"""
Include from the project urls.py, above the 'controlroom/' admin route:
    path('controlroom/people/', include('User.admin_urls')),
Names are all prefixed usr_admin_ so they cannot clash with your existing User url names.
"""
from django.urls import path

from . import admin_views as v

urlpatterns = [
    path('', v.user_list, name='usr_admin_list'),
    path('<int:pk>/', v.user_detail, name='usr_admin_detail'),
    path('<int:pk>/deactivate/', v.user_deactivate, name='usr_admin_deactivate'),
    path('<int:pk>/reactivate/', v.user_reactivate, name='usr_admin_reactivate'),
    path('<int:pk>/staff/', v.user_staff, name='usr_admin_staff'),
    path('<int:pk>/verify-email/', v.user_verify_email, name='usr_admin_verify_email'),
    path('<int:pk>/clear/<slug:what>/', v.user_clear_profile, name='usr_admin_clear'),
    path('<int:pk>/privilege/<slug:field>/', v.user_privilege, name='usr_admin_privilege'),
    path('locations/', v.location_list, name='usr_admin_locations'),
    path('locations/add/', v.state_add, name='usr_admin_state_add'),
    path('locations/<int:pk>/', v.state_detail, name='usr_admin_state'),
    path('locations/<int:pk>/update/', v.state_update, name='usr_admin_state_update'),
    path('locations/<int:pk>/lga/add/', v.lga_add, name='usr_admin_lga_add'),
    path('locations/lga/<int:pk>/update/', v.lga_update, name='usr_admin_lga_update'),
    path('overview/', v.overview, name='usr_admin_overview'),
    path('overview/run/<slug:action>/', v.tool_run, name='usr_admin_tool'),
]
