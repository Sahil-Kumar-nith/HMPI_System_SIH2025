# Enhanced URLs configuration for interactive maps
from django.urls import path, include
from rest_framework import routers
from . import views
from .views import SampleViewSet

router = routers.DefaultRouter()
router.register(r'samples', SampleViewSet)

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    path('api/map-data/', views.map_data_api, name='map_data_api'),
    
    # Regular Django URLs
    path('', views.home, name='home'),
    path('samples/', views.sample_list, name='sample_list'),
    path('add/', views.add_sample, name='add_sample'),
    path('upload-csv/', views.upload_csv, name='upload_csv'),
    path('samples-with-hpi/', views.sample_with_hpi_list, name='sample_with_hpi_list'),  # Fixed this line
    path('ml-analysis/', views.ml_analysis, name='ml_analysis'),
    # In your urls.py, make sure you have:
    path('filtered-samples/', views.filtered_sample_list, name='filtered_sample_list'),
    path('sample/<int:pk>/', views.sample_detail, name='sample_detail'),
    path('voice-query-api/', views.voice_query_api, name='voice_query_api'),
    path('water-quality/', views.water_quality, name='water_quality'),
    
    # Enhanced Interactive Maps URLs
    path('interactive-maps/', views.interactive_maps, name='interactive_maps'),
    path('export-map-data/', views.export_map_data, name='export_map_data'),
    path('generate-map-report/', views.generate_map_report, name='generate_map_report'),
]
