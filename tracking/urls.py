from django.urls import path
from . import views

urlpatterns = [
    path('', views.tracking_page, name='tracking_page'),       
    path('register/', views.register, name='register'),        
    path('start/', views.start_tracking, name='start_tracking'),  
    path('stop/<int:session_id>/', views.stop_tracking, name='stop_tracking'), 
    path('get-route/', views.get_route, name='get_route'),
    path('session-map/<int:session_id>/', views.session_map, name='session_map'),
    path('admin/logout_on_tab_close/', views.logout_on_tab_close, name='logout_on_tab_close'),
    path("my-tracks/", views.my_tracks, name="my_tracks"),
]

