from django.urls import path, re_path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Student Registration
    path('register-student/', views.register_student, name='register-student'),
    path('register-staff/', views.register_staff, name='register-staff'),
    
    # Authentication
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    
    # Face Processing API
    path('process-face/', views.process_face_api, name='process_face_api'),
    
    # Password Reset - ONLY ONE, use the working one
    path('password-reset/', views.password_reset_request, name='password_reset'),  # ← REMOVED the debug one
    path('password-reset/confirm/<uidb64>/<token>/', 
         views.password_reset_confirm_view, 
         name='password_reset_confirm'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    
    path('password-reset-complete/',
         views.password_reset_complete_custom,
         name='password_reset_complete'),
    
]