import csv
import json
import spacy
from spacy.matcher import Matcher, PhraseMatcher
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Sample
from .forms import GroundwaterSampleForm, CsvUploadForm, SampleFilterForm
from .utils import calculate_HPI, analyze_sample
from .ml_utils import HMPIDataAnalyzer, create_individual_graph

# --- Sample Views ---

import csv
import json
import spacy
from spacy.matcher import Matcher, PhraseMatcher
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from .models import Sample
from .forms import GroundwaterSampleForm, CsvUploadForm, SampleFilterForm
from .utils import calculate_HPI, analyze_sample
from .ml_utils import HMPIDataAnalyzer, create_individual_graph
from .serializers import SampleSerializer

class SampleViewSet(viewsets.ModelViewSet):
    queryset = Sample.objects.all().order_by('-date', '-id')
    serializer_class = SampleSerializer


# --- Sample Views ---

def home(request):
    total_samples = Sample.objects.count()
    locations_count = Sample.objects.values('location').distinct().count()
    
    unsafe_samples = 0
    samples = Sample.objects.all()
    for sample in samples:
        is_drinkable, _ = analyze_sample(sample)
        if not is_drinkable:
            unsafe_samples += 1
    
    total_hpi = 0
    hpi_count = 0
    for sample in samples:
        conc_dict = {
            'lead': sample.lead,
            'mercury': sample.mercury,
            'cadmium': sample.cadmium,
            'arsenic': sample.arsenic,
        }
        hpi = calculate_HPI(conc_dict)
        if hpi > 0:
            total_hpi += hpi
            hpi_count += 1
    
    avg_hpi = total_hpi / hpi_count if hpi_count > 0 else 0
    
    context = {
        'total_samples': total_samples,
        'locations_count': locations_count,
        'unsafe_samples': unsafe_samples,
        'avg_hpi': avg_hpi,
    }
    return render(request, 'hmpi_system_app/home.html', context)

# [Include the rest of your views exactly as previously provided, unchanged]


    """Enhanced home view with statistics"""
    total_samples = Sample.objects.count()
    locations_count = Sample.objects.values('location').distinct().count()
    
    # Calculate unsafe samples
    unsafe_samples = 0
    samples = Sample.objects.all()
    for sample in samples:
        is_drinkable, _ = analyze_sample(sample)
        if not is_drinkable:
            unsafe_samples += 1
    
    # Calculate average HPI
    total_hpi = 0
    hpi_count = 0
    for sample in samples:
        conc_dict = {
            'lead': sample.lead,
            'mercury': sample.mercury,
            'cadmium': sample.cadmium,
            'arsenic': sample.arsenic,
        }
        hpi = calculate_HPI(conc_dict)
        if hpi > 0:
            total_hpi += hpi
            hpi_count += 1
    
    avg_hpi = total_hpi / hpi_count if hpi_count > 0 else 0
    
    context = {
        'total_samples': total_samples,
        'locations_count': locations_count,
        'unsafe_samples': unsafe_samples,
        'avg_hpi': avg_hpi,
    }
    return render(request, 'hmpi_system_app/home.html', context)

from django.shortcuts import render
from django.db.models import Q
from .models import Sample

from django.shortcuts import render
from django.db.models import Count
from .models import Sample

def sample_list(request):
    samples = Sample.objects.all()
    unique_locations = samples.values('location').distinct().count()
    high_contamination_count = samples.filter(
        Q(lead__gt=0.01) | Q(mercury__gt=0.006) | Q(cadmium__gt=0.003) | Q(arsenic__gt=0.01)
    ).count()
    context = {
        'samples': samples,
        'unique_locations': unique_locations,
        'high_contamination_count': high_contamination_count,
    }
    return render(request, 'hmpi_system_app/sample_list.html', context)


def add_sample(request):
    if request.method == "POST":
        form = GroundwaterSampleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('sample_list')
    else:
        form = GroundwaterSampleForm()
    return render(request, 'hmpi_system_app/add_sample.html', {'form': form})

def upload_csv(request):
    message = None
    error = None
    
    if request.method == "POST":
        form = CsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                csv_file = request.FILES['csv_file']
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                
                created_count = 0
                for row in reader:
                    Sample.objects.create(
                        location=row['location'],
                        date=row['date'],
                        lead=float(row['lead']),
                        mercury=float(row['mercury']),
                        cadmium=float(row['cadmium']),
                        arsenic=float(row['arsenic']),
                        latitude=float(row.get('latitude', 0)) if row.get('latitude') else None,
                        longitude=float(row.get('longitude', 0)) if row.get('longitude') else None,
                    )
                    created_count += 1
                
                message = f"Successfully imported {created_count} samples."
                return redirect('sample_list')
            except Exception as e:
                error = f"Error processing CSV file: {str(e)}"
    else:
        form = CsvUploadForm()
    
    return render(request, 'hmpi_system_app/upload_csv.html', {
        'form': form,
        'message': message,
        'error': error
    })

def sample_with_hpi_list(request):
    """Enhanced HPI analysis view with proper calculations"""
    samples = Sample.objects.all().order_by('-date', '-id')
    
    # Calculate HPI for each sample and analyze drinkability
    analyzed_samples = []
    for sample in samples:
        conc_dict = {
            'lead': sample.lead,
            'mercury': sample.mercury,
            'cadmium': sample.cadmium,
            'arsenic': sample.arsenic,
        }
        
        hpi = calculate_HPI(conc_dict)
        is_drinkable, filters = analyze_sample(sample)
        
        # Add calculated values to sample object
        sample.hpi_score = hpi
        sample.is_drinkable = is_drinkable
        sample.suggested_filters = filters
        
        analyzed_samples.append(sample)
    
    # Calculate statistics
    total_samples = len(analyzed_samples)
    safe_samples = len([s for s in analyzed_samples if s.is_drinkable])
    unsafe_samples = total_samples - safe_samples
    
    context = {
        'samples': analyzed_samples,
        'total_samples': total_samples,
        'safe_samples': safe_samples,
        'unsafe_samples': unsafe_samples,
    }
    
    return render(request, 'hmpi_system_app/sample_with_hpi.html', context)


def ml_analysis(request):
    samples = Sample.objects.all()
    if not samples.exists():
        return render(request, 'hmpi_system_app/ml_analysis.html', {
            'error': 'No samples available for analysis. Please add some samples first.'
        })
    try:
        analyzer = HMPIDataAnalyzer(samples)
        context = {
            'correlation_plot': analyzer.create_correlation_matrix(),
            'simultaneous_plots': analyzer.create_simultaneous_plots(),
            'geopandas_plot': analyzer.create_geopandas_plot(),
            'interactive_map': analyzer.create_folium_map(),
            'ml_results': analyzer.train_ml_model()
        }
    except Exception as e:
        context = {
            'error': f'Error generating analysis: {str(e)}'
        }
    
    return render(request, 'hmpi_system_app/ml_analysis.html', context)

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from .models import Sample
from .utils import calculate_HPI, analyze_sample

def filtered_sample_list(request):
    """Enhanced filtering view with advanced search capabilities"""
    
    # Get all samples initially
    samples = Sample.objects.all().order_by('-date', '-id')
    
    # Quick search
    search_query = request.GET.get('q', '').strip()
    if search_query:
        samples = samples.filter(
            Q(location__icontains=search_query) |
            Q(id__icontains=search_query)
        )
    
    # Location filtering
    selected_locations = request.GET.getlist('locations')
    if selected_locations:
        samples = samples.filter(location__in=selected_locations)
    
    # Date range filtering
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        samples = samples.filter(date__gte=date_from)
    if date_to:
        samples = samples.filter(date__lte=date_to)
    
    # Metal concentration filtering
    metals = ['lead', 'mercury', 'cadmium', 'arsenic']
    for metal in metals:
        if request.GET.get(f'filter_{metal}'):
            min_val = float(request.GET.get(f'{metal}_min', 0))
            max_val = float(request.GET.get(f'{metal}_max', 1))
            samples = samples.filter(**{f'{metal}__gte': min_val, f'{metal}__lte': max_val})
    
    # HPI range filtering
    hpi_min = request.GET.get('hpi_min', '0')
    hpi_max = request.GET.get('hpi_max', '300')
    if hpi_min != '0' or hpi_max != '300':
        # Calculate HPI for filtering (this would be better done with a database field)
        filtered_samples = []
        for sample in samples:
            conc_dict = {
                'lead': sample.lead,
                'mercury': sample.mercury,
                'cadmium': sample.cadmium,
                'arsenic': sample.arsenic,
            }
            hpi = calculate_HPI(conc_dict)
            if float(hpi_min) <= hpi <= float(hpi_max):
                sample.hpi_score = hpi  # Add HPI to sample object
                filtered_samples.append(sample)
        samples = filtered_samples
    else:
        # Add HPI to all samples
        for sample in samples:
            conc_dict = {
                'lead': sample.lead,
                'mercury': sample.mercury,
                'cadmium': sample.cadmium,
                'arsenic': sample.arsenic,
            }
            sample.hpi_score = calculate_HPI(conc_dict)
    
    # Safety status filtering
    safety_statuses = request.GET.getlist('safety_status')
    if safety_statuses:
        if isinstance(samples, list):
            # Already filtered by HPI, work with list
            safety_filtered = []
            for sample in samples:
                is_drinkable, _ = analyze_sample(sample)
                sample.is_drinkable = is_drinkable
                
                if ('drinkable' in safety_statuses and is_drinkable) or \
                   ('not_drinkable' in safety_statuses and not is_drinkable):
                    safety_filtered.append(sample)
            samples = safety_filtered
        else:
            # Filter queryset based on safety analysis
            safety_filtered = []
            for sample in samples:
                is_drinkable, _ = analyze_sample(sample)
                sample.is_drinkable = is_drinkable
                
                if ('drinkable' in safety_statuses and is_drinkable) or \
                   ('not_drinkable' in safety_statuses and not is_drinkable):
                    safety_filtered.append(sample)
            samples = safety_filtered
    else:
        # Add safety analysis to all samples
        if isinstance(samples, list):
            for sample in samples:
                is_drinkable, _ = analyze_sample(sample)
                sample.is_drinkable = is_drinkable
        else:
            sample_list = []
            for sample in samples:
                is_drinkable, _ = analyze_sample(sample)
                sample.is_drinkable = is_drinkable
                sample_list.append(sample)
            samples = sample_list
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'date')
    if sort_by and isinstance(samples, list):
        if sort_by == 'date':
            samples.sort(key=lambda x: x.date, reverse=True)
        elif sort_by == '-date':
            samples.sort(key=lambda x: x.date)
        elif sort_by == 'location':
            samples.sort(key=lambda x: x.location)
        elif sort_by == 'hpi_score':
            samples.sort(key=lambda x: getattr(x, 'hpi_score', 0))
        elif sort_by == '-hpi_score':
            samples.sort(key=lambda x: getattr(x, 'hpi_score', 0), reverse=True)
    
    # Pagination
    per_page = int(request.GET.get('per_page', 25))
    if isinstance(samples, list):
        # Manual pagination for list
        from django.core.paginator import Paginator
        paginator = Paginator(samples, per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        samples = page_obj
    else:
        paginator = Paginator(samples, per_page)
        page_number = request.GET.get('page')
        samples = paginator.get_page(page_number)
    
    # Calculate statistics
    all_samples = Sample.objects.all()
    total_samples = all_samples.count()
    unique_locations = all_samples.values_list('location', flat=True).distinct()
    
    # Calculate safe/unsafe counts from current filtered results
    if hasattr(samples, 'object_list'):
        current_samples = samples.object_list
    else:
        current_samples = samples
        
    safe_count = sum(1 for s in current_samples if getattr(s, 'is_drinkable', False))
    unsafe_count = len(current_samples) - safe_count
    
    context = {
        'samples': samples,
        'total_samples': total_samples,
        'filtered_count': len(current_samples),
        'unique_locations': unique_locations,
        'safe_count': safe_count,
        'unsafe_count': unsafe_count,
        'request': request,  # Pass request for template access to GET params
    }
    
    return render(request, 'hmpi_system_app/filtered_sample_list.html', context)


def sample_detail(request, pk):
    sample = get_object_or_404(Sample, pk=pk)
    
    try:
        graph = create_individual_graph(sample)
    except Exception:
        graph = None
    
    # Calculate HPI for this sample
    conc_dict = {
        'lead': sample.lead,
        'mercury': sample.mercury,
        'cadmium': sample.cadmium,
        'arsenic': sample.arsenic,
    }
    hpi = calculate_HPI(conc_dict)
    
    # Analyze sample safety
    is_drinkable, filters = analyze_sample(sample)
    
    context = {
        'sample': sample,
        'graph': graph,
        'hpi': hpi,
        'is_drinkable': is_drinkable,
        'filters': filters,
    }
    
    return render(request, 'hmpi_system_app/sample_detail.html', context)

def water_quality(request):
    samples = Sample.objects.all().order_by('-date', '-id')
    analyzed_samples = []
    
    for sample in samples:
        is_drinkable, filters = analyze_sample(sample)
        analyzed_samples.append({
            'sample': sample,
            'is_drinkable': is_drinkable,
            'filters': filters,
        })
    return render(request, 'hmpi_system_app/water_quality.html', {
        'analyzed_samples': analyzed_samples
    })

# --- Voice Assistant with NLP ---

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None
    print("Warning: spaCy English model not found. Install with: python -m spacy download en_core_web_sm")

if nlp:
    matcher = Matcher(nlp.vocab)
    phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    matcher.add("RequestLeadLevel", [[{"LOWER": "lead"}]])
    matcher.add("RequestMercuryLevel", [[{"LOWER": "mercury"}]])
    matcher.add("RequestCadmiumLevel", [[{"LOWER": "cadmium"}]])
    matcher.add("RequestArsenicLevel", [[{"LOWER": "arsenic"}]])
    matcher.add("Help", [[{"LOWER": "help"}], [{"LOWER": "what"}, {"LOWER": "can"}, {"LOWER": "i"}, {"LOWER": "ask"}]])
    site_names = ["site_a", "site_b", "site_c", "site_d", "site_e", "site_f", "site_g", "site_h",
                  "site_i", "site_j", "site_k", "site_l", "site_m", "site_n", "site_o", "site_p"]
    patterns = [nlp.make_doc(site) for site in site_names]
    phrase_matcher.add("SITES", patterns)

def set_context(request, key, value):
    request.session[key] = value

def get_context(request, key):
    return request.session.get(key)

@csrf_exempt
def voice_query_api(request):
    if request.method == "POST":
        if not nlp:
            return JsonResponse({
                "answer": "Voice assistant is not available. Please install spaCy English model."
            })
        try:
            data = json.loads(request.body)
            user_query = data.get("query", "").lower().strip()
        except Exception:
            return JsonResponse({"answer": "Invalid input received."})
        if not user_query:
            return JsonResponse({"answer": "Please say something."})
        doc = nlp(user_query)
        matches = matcher(doc)
        intents = set([nlp.vocab.strings[match_id] for match_id, start, end in matches])
        sites_matches = phrase_matcher(doc)
        sites = [doc[start:end].text for match_id, start, end in sites_matches]
        last_site = get_context(request, "last_site")
        if sites:
            site = sites[0]
            set_context(request, "last_site", site)
        else:
            site = last_site
        if "RequestLeadLevel" in intents:
            if site:
                try:
                    sample = Sample.objects.filter(location__icontains=site).latest('date')
                    answer = f"Lead concentration at {site} is {sample.lead:.3f} mg/L (limit: 0.01 mg/L)."
                except Sample.DoesNotExist:
                    answer = f"No data available for {site}. Please check the location name."
            else:
                answer = "Please specify the site for lead concentration."
        elif "RequestMercuryLevel" in intents:
            if site:
                try:
                    sample = Sample.objects.filter(location__icontains=site).latest('date')
                    answer = f"Mercury concentration at {site} is {sample.mercury:.3f} mg/L (limit: 0.006 mg/L)."
                except Sample.DoesNotExist:
                    answer = f"No data available for {site}. Please check the location name."
            else:
                answer = "Please specify the site for mercury levels."
        elif "RequestCadmiumLevel" in intents:
            if site:
                try:
                    sample = Sample.objects.filter(location__icontains=site).latest('date')
                    answer = f"Cadmium concentration at {site} is {sample.cadmium:.3f} mg/L (limit: 0.003 mg/L)."
                except Sample.DoesNotExist:
                    answer = f"No data available for {site}. Please check the location name."
            else:
                answer = "Please specify the site for cadmium concentration."
        elif "RequestArsenicLevel" in intents:
            if site:
                try:
                    sample = Sample.objects.filter(location__icontains=site).latest('date')
                    answer = f"Arsenic concentration at {site} is {sample.arsenic:.3f} mg/L (limit: 0.01 mg/L)."
                except Sample.DoesNotExist:
                    answer = f"No data available for {site}. Please check the location name."
            else:
                answer = "Please specify the site for arsenic concentration."
        elif "Help" in intents:
            available_locations = list(Sample.objects.values_list('location', flat=True).distinct()[:5])
            locations_text = ", ".join(available_locations) if available_locations else "No locations available"
            answer = (f"You can ask about lead, mercury, cadmium, or arsenic levels "
                      f"at a specific site. Available locations: {locations_text}. "
                      f"For example, say 'What is the lead level at {available_locations[0] if available_locations else 'Site_A'}?'")
        else:
            answer = ("Sorry, I couldn't understand your request. "
                      "Please ask about heavy metal concentrations at a site or say 'help' for assistance.")
        return JsonResponse({"answer": answer})
    return JsonResponse({"answer": "Invalid request method."})
from django.http import JsonResponse
from .models import Sample  # or your model name

def map_data_api(request):
    samples = Sample.objects.all()
    data = []
    for s in samples:
        data.append({
            "id": s.id,
            "location": s.location,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "lead": s.lead,
            "mercury": s.mercury,
            "cadmium": s.cadmium,
            "arsenic": s.arsenic,
        })
    return JsonResponse(data, safe=False)

from django.shortcuts import render
from .models import Sample

def interactive_maps(request):
    samples = Sample.objects.all()
    return render(request, 'hmpi_app/interactive_maps.html', {'samples': samples})

from django.http import JsonResponse
from .models import Sample

def export_map_data(request):
    samples = Sample.objects.all()
    data = []
    for s in samples:
        data.append({
            "id": s.id,
            "location": s.location,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "lead": s.lead,
            "mercury": s.mercury,
            "cadmium": s.cadmium,
            "arsenic": s.arsenic,
        })
    return JsonResponse(data, safe=False)
from django.shortcuts import render
from django.http import JsonResponse
from .models import Sample

def generate_map_report(request):
    # Example: return a report page or JSON report of map/sample data
    
    samples = Sample.objects.all()
    # prepare report data - you can add actual logic here
    
    context = {
        "samples_count": samples.count(),
        # Add more report data if needed
    }
    
    # Render a template or return JSON
    return render(request, 'hmpi_system_app/map_report.html', context)
    
    # Or if JSON:
    # data = {...}
    # return JsonResponse(data)
