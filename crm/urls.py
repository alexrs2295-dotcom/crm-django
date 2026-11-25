from django.urls import path

from . import views

urlpatterns = [
    path('', views.ClientListView.as_view(), name='client_list'),
    path('clientes/exportar/', views.ClientExportView.as_view(), name='client_export'),
    path('estadisticas/', views.StatsView.as_view(), name='stats'),
    path('clientes/nuevo/', views.ClientCreateView.as_view(), name='client_create'),
    path('clientes/<int:pk>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('clientes/<int:pk>/editar/', views.ClientUpdateView.as_view(), name='client_update'),
    path('clientes/<int:pk>/eliminar/', views.ClientDeleteView.as_view(), name='client_delete'),
    path('clientes/<int:client_pk>/interacciones/nueva/', views.InteractionCreateView.as_view(), name='interaction_create'),
    path('interacciones/<int:pk>/editar/', views.InteractionUpdateView.as_view(), name='interaction_update'),
    path('interacciones/<int:pk>/eliminar/', views.InteractionDeleteView.as_view(), name='interaction_delete'),
    path('empresas/', views.CompanyListView.as_view(), name='company_list'),
    path('empresas/nueva/', views.CompanyCreateView.as_view(), name='company_create'),
    path('empresas/<int:pk>/editar/', views.CompanyUpdateView.as_view(), name='company_update'),
    path('empresas/<int:pk>/eliminar/', views.CompanyDeleteView.as_view(), name='company_delete'),
]
