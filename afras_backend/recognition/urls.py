from django.urls import path
from . import views

urlpatterns = [
    path('video_feed/', views.video_feed, name='video_feed'),
    path('scan_face/', views.scan_face, name='scan_face'),
]
