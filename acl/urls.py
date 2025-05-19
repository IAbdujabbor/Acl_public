from django.urls import path
from django.contrib import admin  # You need to import `admin` for the admin panel route
from acl import views
from django.contrib import admin
from django.urls import path


urlpatterns = [
    path('', views.process_input, name='main'),
    path('chart/', views.chart_data, name='chart_data'),
   
    # This should be a path, and `admin` needs to be imported
]
