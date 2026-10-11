import csv
import json
import re

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets

from .forms import GroundwaterSampleForm, CsvUploadForm
from .models import Sample
from .serializers import SampleSerializer
from .utils import calculate_HPI, analyze_sample

# NOTE: heavy libraries (pandas, geopandas, folium, sklearn, matplotlib) live in
# .ml_utils and are imported lazily inside the views that need them, so the
# rest of the site still works on Vercel (250 MB serverless size limit).


# --- API ---

class SampleViewSet(viewsets.ModelViewSet):
    queryset = Sample.objects.all().order_by('-date', '-id')
    serializer_class = SampleSerializer


# --- Helpers ---

def _conc_dict(sample):
    return {
        'lead': sample.lead,
        'mercury': sample.mercury,
        'cadmium': sample.cadmium,
        'arsenic': sample.arsenic,
    }


def _to_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --- Sample Views ---

def home(request):
    """Home view with statistics"""
    total_samples = Sample.objects.count()
    locations_count = Sample.objects.values('location').distinct().count()

    unsafe_samples = 0
    total_hpi = 0
    hpi_count = 0

    for sample in Sample.objects.all():
        is_drinkable, _ = analyze_sample(sample)
        if not is_drinkable:
            unsafe_samples += 1

        hpi = calculate_HPI(_conc_dict(sample))
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
                        latitude=float(row['latitude']) if row.get('latitude') else None,
                        longitude=float(row['longitude']) if row.get('longitude') else None,
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
        'error': error,
    })


def sample_with_hpi_list(request):
    """HPI analysis view with calculations"""
    samples = Sample.objects.all().order_by('-date', '-id')

    analyzed_samples = []
    for sample in samples:
        hpi = calculate_HPI(_conc_dict(sample))
        is_drinkable, filters = analyze_sample(sample)

        sample.hpi_score = hpi
        sample.is_drinkable = is_drinkable
        sample.suggested_filters = filters
        analyzed_samples.append(sample)

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
        # Lazy import: pandas / geopandas / folium / sklearn are too heavy for Vercel
        from .ml_utils import HMPIDataAnalyzer

        analyzer = HMPIDataAnalyzer(samples)
        context = {
            'correlation_plot': analyzer.create_correlation_matrix(),
            'simultaneous_plots': analyzer.create_simultaneous_plots(),
            'geopandas_plot': analyzer.create_geopandas_plot(),
            'interactive_map': analyzer.create_folium_map(),
            'ml_results': analyzer.train_ml_model(),
        }
    except Exception as e:
        context = {
            'error': f'ML analysis is not available in this deployment: {str(e)}'
        }

    return render(request, 'hmpi_system_app/ml_analysis.html', context)


def filtered_sample_list(request):
    """Filtering view with advanced search capabilities"""

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
    for metal in ['lead', 'mercury', 'cadmium', 'arsenic']:
        if request.GET.get(f'filter_{metal}'):
            min_val = _to_float(request.GET.get(f'{metal}_min'), 0)
            max_val = _to_float(request.GET.get(f'{metal}_max'), 1)
            samples = samples.filter(**{f'{metal}__gte': min_val, f'{metal}__lte': max_val})

    # HPI range filtering (HPI is calculated, not stored, so filter in Python)
    hpi_min_raw = request.GET.get('hpi_min', '0')
    hpi_max_raw = request.GET.get('hpi_max', '300')
    hpi_min = _to_float(hpi_min_raw, 0)
    hpi_max = _to_float(hpi_max_raw, 300)

    sample_items = []
    for sample in samples:
        hpi = calculate_HPI(_conc_dict(sample))
        sample.hpi_score = hpi
        if hpi_min_raw != '0' or hpi_max_raw != '300':
            if not (hpi_min <= hpi <= hpi_max):
                continue
        sample_items.append(sample)

    # Safety status filtering / annotation
    safety_statuses = request.GET.getlist('safety_status')
    final_samples = []
    for sample in sample_items:
        is_drinkable, _ = analyze_sample(sample)
        sample.is_drinkable = is_drinkable
        if safety_statuses:
            if ('drinkable' in safety_statuses and is_drinkable) or \
               ('not_drinkable' in safety_statuses and not is_drinkable):
                final_samples.append(sample)
        else:
            final_samples.append(sample)
    sample_items = final_samples

    # Sorting
    sort_by = request.GET.get('sort_by', 'date')
    if sort_by == 'date':
        sample_items.sort(key=lambda x: x.date, reverse=True)
    elif sort_by == '-date':
        sample_items.sort(key=lambda x: x.date)
    elif sort_by == 'location':
        sample_items.sort(key=lambda x: x.location)
    elif sort_by == 'hpi_score':
        sample_items.sort(key=lambda x: getattr(x, 'hpi_score', 0))
    elif sort_by == '-hpi_score':
        sample_items.sort(key=lambda x: getattr(x, 'hpi_score', 0), reverse=True)

    # Pagination
    try:
        per_page = int(request.GET.get('per_page', 25))
    except ValueError:
        per_page = 25
    paginator = Paginator(sample_items, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Statistics
    all_samples = Sample.objects.all()
    total_samples = all_samples.count()
    unique_locations = all_samples.values_list('location', flat=True).distinct()

    current_samples = page_obj.object_list
    safe_count = sum(1 for s in current_samples if getattr(s, 'is_drinkable', False))
    unsafe_count = len(current_samples) - safe_count

    context = {
        'samples': page_obj,
        'total_samples': total_samples,
        'filtered_count': len(sample_items),
        'unique_locations': unique_locations,
        'safe_count': safe_count,
        'unsafe_count': unsafe_count,
        'request': request,
    }
    return render(request, 'hmpi_system_app/filtered_sample_list.html', context)


def sample_detail(request, pk):
    sample = get_object_or_404(Sample, pk=pk)

    try:
        # Lazy import so a missing/heavy plotting library doesn't break the site
        from .ml_utils import create_individual_graph
        graph = create_individual_graph(sample)
    except Exception:
        graph = None

    hpi = calculate_HPI(_conc_dict(sample))
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


# --- Voice Assistant (lightweight keyword matching, no spaCy) ---

METAL_INFO = {
    'lead': ('lead', 0.01),
    'mercury': ('mercury', 0.006),
    'cadmium': ('cadmium', 0.003),
    'arsenic': ('arsenic', 0.01),
}

SITE_PATTERN = re.compile(r'\bsite[\s_\-]?([a-p])\b')
HELP_PATTERN = re.compile(r'\bhelp\b|what can i ask')


def set_context(request, key, value):
    request.session[key] = value


def get_context(request, key):
    return request.session.get(key)


def _find_site(query):
    """Return a site name like 'site_a' if mentioned in the query, else None."""
    match = SITE_PATTERN.search(query)
    if match:
        return f"site_{match.group(1)}"
    return None


@csrf_exempt
def voice_query_api(request):
    if request.method != "POST":
        return JsonResponse({"answer": "Invalid request method."})

    try:
        data = json.loads(request.body)
        user_query = data.get("query", "").lower().strip()
    except Exception:
        return JsonResponse({"answer": "Invalid input received."})

    if not user_query:
        return JsonResponse({"answer": "Please say something."})

    # Intent detection
    metal = next((m for m in METAL_INFO if re.search(rf'\b{m}\b', user_query)), None)
    is_help = bool(HELP_PATTERN.search(user_query))

    # Site detection (with conversation memory via session)
    site = _find_site(user_query)
    if site:
        try:
            set_context(request, "last_site", site)
        except Exception:
            pass
    else:
        try:
            site = get_context(request, "last_site")
        except Exception:
            site = None

    if metal:
        label, limit = METAL_INFO[metal]
        if not site:
            answer = f"Please specify the site for {label} concentration."
        else:
            try:
                sample = Sample.objects.filter(location__icontains=site).latest('date')
                value = getattr(sample, metal)
                answer = f"{label.capitalize()} concentration at {site} is {value:.3f} mg/L (limit: {limit} mg/L)."
            except Sample.DoesNotExist:
                answer = f"No data available for {site}. Please check the location name."
    elif is_help:
        available_locations = list(Sample.objects.values_list('location', flat=True).distinct()[:5])
        locations_text = ", ".join(available_locations) if available_locations else "No locations available"
        example_site = available_locations[0] if available_locations else 'Site_A'
        answer = (f"You can ask about lead, mercury, cadmium, or arsenic levels "
                  f"at a specific site. Available locations: {locations_text}. "
                  f"For example, say 'What is the lead level at {example_site}?'")
    else:
        answer = ("Sorry, I couldn't understand your request. "
                  "Please ask about heavy metal concentrations at a site or say 'help' for assistance.")

    return JsonResponse({"answer": answer})


# --- Maps ---

def _map_rows():
    return [
        {
            "id": s.id,
            "location": s.location,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "lead": s.lead,
            "mercury": s.mercury,
            "cadmium": s.cadmium,
            "arsenic": s.arsenic,
        }
        for s in Sample.objects.all()
    ]


def map_data_api(request):
    return JsonResponse(_map_rows(), safe=False)


def export_map_data(request):
    return JsonResponse(_map_rows(), safe=False)


def interactive_maps(request):
    samples = Sample.objects.all()
    # NOTE: template path was 'hmpi_app/...' before; confirm the template really
    # lives in hmpi_system_app/templates/hmpi_system_app/interactive_maps.html
    return render(request, 'hmpi_system_app/interactive_maps.html', {'samples': samples})


def generate_map_report(request):
    samples = Sample.objects.all()
    context = {
        "samples_count": samples.count(),
    }
    return render(request, 'hmpi_system_app/map_report.html', context)
