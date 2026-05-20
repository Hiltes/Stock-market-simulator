from django.urls import path

from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/start/', views.api_start_simulation, name='api_start_simulation'),
    path('api/action/', views.api_action, name='api_action'),
    path('api/history/', views.api_history, name='api_history'),
]
