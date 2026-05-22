from django.urls import path
from energy import views

urlpatterns = [
    path('reports/weekly/', views.weekly_report, name='weekly_report'),
    path('reports/whatif/', views.whatif, name='whatif'),
]