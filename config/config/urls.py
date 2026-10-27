from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('/login/')),  # 👈 ESTO
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]