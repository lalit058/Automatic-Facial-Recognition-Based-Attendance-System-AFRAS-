from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.shortcuts import render
from dashboard.views import home
from django.views.generic import TemplateView

def home(request):
    return render(request, 'home.html')

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('attendance/', include('attendance.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('recognition/', include('recognition.urls')),
    
    path('test-register/', TemplateView.as_view(template_name='accounts/register.html')),
    path('test-login/', TemplateView.as_view(template_name='accounts/login.html')),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
