from django.urls import path

from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/start', views.api_start_simulation, name='api_start_simulation'),
    path('api/start/', views.api_start_simulation),
    path('api/decision', views.api_decision, name='api_decision'),
    path('api/decision/', views.api_decision),
    path('api/action', views.api_action, name='api_action_legacy'),
    path('api/action/', views.api_action),
    path('api/history', views.api_history, name='api_history'),
    path('api/history/', views.api_history),
]
