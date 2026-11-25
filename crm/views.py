import csv
import re
from datetime import timedelta
from itertools import groupby

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.http import urlencode
from django.utils import timezone
from django.utils.text import capfirst
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView,
)

from .forms import InteractionForm
from .models import Client, Company, Interaction


class FormularioMixin(SuccessMessageMixin):
    """Plantilla común de formulario y borrado, con título."""
    template_name = 'crm/form.html'
    titulo = ''

    def get_context_data(self, **kwargs):
        return super().get_context_data(titulo=self.titulo, **kwargs)


class BorrarMixin(SuccessMessageMixin):
    template_name = 'crm/confirm_delete.html'
    success_message = 'Eliminado correctamente.'

    def form_valid(self, form):
        # borrado con "deshacer": sin mensaje ni redirección; el JS solo da por bueno un 204
        if self.request.headers.get('X-Silent'):
            self.object.delete()
            return HttpResponse(status=204)
        return super().form_valid(form)


# --- Clientes ---------------------------------------------------------------

class ClientesPropiosMixin(LoginRequiredMixin):
    """Cada comercial solo ve sus clientes; el superuser ve todos."""
    def get_queryset(self):
        qs = Client.objects.select_related('company', 'comercial')
        if self.request.user.is_superuser:
            return qs
        return qs.filter(comercial=self.request.user)


ORDENES = {
    'nombre': ('nombre', 'apellidos', 'pk'),
    '-nombre': ('-nombre', '-apellidos', '-pk'),
    'empresa': (F('company__nombre').asc(nulls_last=True), 'nombre', 'pk'),
    '-empresa': (F('company__nombre').desc(nulls_last=True), 'nombre', 'pk'),
    'alta': ('creado', 'pk'),
    '-alta': ('-creado', '-pk'),
}
ORDEN_LABELS = [
    ('', 'Nombre (A-Z)'), ('-nombre', 'Nombre (Z-A)'),
    ('empresa', 'Empresa (A-Z)'), ('-empresa', 'Empresa (Z-A)'),
    ('alta', 'Alta (antiguos primero)'), ('-alta', 'Alta (recientes primero)'),
]
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _id(valor):
    """Entero positivo razonable o None."""
    return int(valor) if valor and valor.isascii() and valor.isdigit() and len(valor) <= 9 else None


class ClientListView(ClientesPropiosMixin, ListView):
    paginate_by = 10

    def paginate_queryset(self, queryset, page_size):
        # página fuera de rango o no numérica: la última válida
        paginator = self.get_paginator(queryset, page_size, allow_empty_first_page=self.get_allow_empty())
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def parsear(self):
        """Parámetros GET válidos (lista blanca); lo demás se ignora."""
        g, user = self.request.GET, self.request.user
        p = {}
        if q := g.get('q', '').strip():
            p['q'] = q
        if (v := _id(g.get('empresa'))) is not None:
            p['empresa'] = v
        if user.is_superuser and (v := _id(g.get('comercial'))) is not None:
            p['comercial'] = v
        if g.get('tipo') in dict(Interaction.TIPOS):
            p['tipo'] = g['tipo']
        if re.fullmatch(r'[1-9]\d{3}-(0[1-9]|1[0-2])', g.get('mes', '')):
            p['mes'] = g['mes']
        if g.get('orden') in ORDENES:
            p['orden'] = g['orden']
        return p

    def get_queryset(self):
        qs, p = super().get_queryset(), self.parsear()
        if 'q' in p:
            q = p['q']
            qs = qs.filter(
                Q(nombre__icontains=q) | Q(apellidos__icontains=q)
                | Q(email__icontains=q) | Q(company__nombre__icontains=q)
            )
        if 'empresa' in p:
            qs = qs.filter(company_id=p['empresa'])
        if 'comercial' in p:
            qs = qs.filter(comercial_id=p['comercial'])
        if 'tipo' in p or 'mes' in p:
            inter = Interaction.objects.all()
            if 'tipo' in p:
                inter = inter.filter(tipo=p['tipo'])
            if 'mes' in p:
                y, m = p['mes'].split('-')
                inter = inter.filter(fecha__year=int(y), fecha__month=int(m))
            qs = qs.filter(pk__in=inter.values('client'))  # sin duplicados
        if 'orden' in p:
            qs = qs.order_by(*ORDENES[p['orden']])
        return qs

    def get_context_data(self, **kwargs):
        p = self.parsear()
        user = self.request.user
        base = super().get_queryset()  # solo los clientes visibles para el usuario

        def qs(*quitar, **extra):
            d = {k: v for k, v in p.items() if k not in quitar}
            return urlencode({**d, **extra})

        actual = p.get('orden', 'nombre')
        sort = {}
        for col in ('nombre', 'empresa', 'alta'):
            d = 'asc' if actual == col else 'desc' if actual == '-' + col else 'none'
            sort[col] = {'dir': d, 'href': '?' + qs('orden', orden='-' + col if d == 'asc' else col),
                         'aria': {'asc': 'ascending', 'desc': 'descending', 'none': 'none'}[d]}

        empresas = Company.objects.filter(pk__in=base.exclude(company=None).values('company'))
        comerciales = (get_user_model().objects.filter(pk__in=base.values('comercial'))
                       if user.is_superuser else None)
        chips = []
        if 'empresa' in p:
            nombre = Company.objects.filter(pk=p['empresa']).values_list('nombre', flat=True).first()
            chips.append(('Empresa: ' + (nombre or '?'), qs('empresa')))
        if 'comercial' in p:
            u = get_user_model().objects.filter(pk=p['comercial']).first()
            chips.append(('Comercial: ' + (capfirst(u.get_username()) if u else '?'), qs('comercial')))
        if 'tipo' in p:
            chips.append(('Interacción: ' + dict(Interaction.TIPOS)[p['tipo']], qs('tipo')))
        if 'mes' in p:
            y, m = p['mes'].split('-')
            chips.append((f'Interacciones: {capfirst(MESES[int(m) - 1])} {y}', qs('mes')))

        return super().get_context_data(
            q=p.get('q', ''), orden=p.get('orden', ''), sort=sort, chips=chips,
            empresas=empresas, comerciales=comerciales, empresa_id=p.get('empresa'),
            comercial_id=p.get('comercial'), ordenes=ORDEN_LABELS,
            qs_todo=qs(), qs_limpiar=qs('empresa', 'comercial', 'tipo', 'mes'),
            hidden={k: p[k] for k in ('tipo', 'mes') if k in p}, **kwargs)


class ClientExportView(ClientListView):
    """CSV para Excel (es): mismo queryset y filtro ?q= que la lista."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="clientes.csv"'
        response.write('﻿')  # BOM para que Excel detecte UTF-8
        w = csv.writer(response, delimiter=';')
        w.writerow(['Nombre', 'Apellidos', 'Email', 'Teléfono', 'Empresa',
                    'Comercial', 'Interacciones', 'Fecha de alta'])
        for c in self.get_queryset().annotate(n_inter=Count('interactions')):
            w.writerow([_csv_seguro(v) for v in (
                c.nombre, c.apellidos, c.email, c.telefono, c.company or '',
                c.comercial, c.n_inter,
                timezone.localtime(c.creado).strftime('%d/%m/%Y'))])
        return response


def _csv_seguro(valor):
    """Evita inyección de fórmulas en Excel."""
    valor = str(valor)
    return "'" + valor if valor.startswith(('=', '+', '-', '@', '\t', '\r')) else valor


class ClientDetailView(ClientesPropiosMixin, DetailView):
    def get_context_data(self, **kwargs):
        c = self.object
        grupos = [
            {'fecha': items[0].fecha, 'items': items}
            for _, g in groupby(
                c.interactions.select_related('usuario'),
                key=lambda i: (timezone.localtime(i.fecha).year, timezone.localtime(i.fecha).month))
            for items in [list(g)]
        ]
        return super().get_context_data(
            grupos=grupos, tipos=Interaction.TIPOS,
            iniciales=(c.nombre[:1] + c.apellidos[:1]).upper() or '?',
            ahora=timezone.localtime().strftime('%Y-%m-%dT%H:%M'), **kwargs)


class ClientFormMixin(FormularioMixin):
    model = Client
    fields = ['nombre', 'apellidos', 'email', 'telefono', 'company', 'comercial']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.request.user.is_superuser:
            del form.fields['comercial']  # se asigna al usuario que crea
        else:
            form.fields['comercial'].label_from_instance = lambda u: capfirst(u.get_username())
            if not form.instance.pk:
                form.fields['comercial'].initial = self.request.user
        return form

    def form_valid(self, form):
        if not self.request.user.is_superuser and not form.instance.pk:
            form.instance.comercial = self.request.user
        return super().form_valid(form)


class ClientCreateView(ClientFormMixin, ClientesPropiosMixin, CreateView):
    titulo = 'Nuevo cliente'
    success_message = 'Cliente creado.'


class ClientUpdateView(ClientFormMixin, ClientesPropiosMixin, UpdateView):
    titulo = 'Editar cliente'
    success_message = 'Cliente actualizado.'


class ClientDeleteView(BorrarMixin, ClientesPropiosMixin, DeleteView):
    success_url = reverse_lazy('client_list')


# --- Interacciones ----------------------------------------------------------

class InteraccionesPropiasMixin(LoginRequiredMixin):
    def get_queryset(self):
        qs = Interaction.objects.select_related('client')
        if self.request.user.is_superuser:
            return qs
        return qs.filter(client__comercial=self.request.user)

    def get_success_url(self):
        return reverse('client_detail', args=[self.object.client_id])


class InteractionCreateView(FormularioMixin, ClientesPropiosMixin, CreateView):
    model = Interaction
    form_class = InteractionForm
    titulo = 'Nueva interacción'
    success_message = 'Interacción creada.'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.client = get_object_or_404(self.get_queryset(), pk=kwargs['client_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.client = self.client
        form.instance.usuario = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('client_detail', args=[self.client.pk])


class InteractionUpdateView(FormularioMixin, InteraccionesPropiasMixin, UpdateView):
    form_class = InteractionForm
    titulo = 'Editar interacción'
    success_message = 'Interacción actualizada.'


class InteractionDeleteView(BorrarMixin, InteraccionesPropiasMixin, DeleteView):
    pass


# --- Estadísticas -----------------------------------------------------------

class StatsView(LoginRequiredMixin, TemplateView):
    template_name = 'crm/stats.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        clientes, inters = Client.objects.all(), Interaction.objects.all()
        if not user.is_superuser:
            clientes = clientes.filter(comercial=user)
            inters = inters.filter(client__comercial=user)

        ahora = timezone.localtime()
        meses = []  # los 6 últimos, del más antiguo al actual
        y, m = ahora.year, ahora.month
        for _ in range(6):
            meses.append((y, m))
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        meses.reverse()
        inicio = ahora.replace(year=meses[0][0], month=meses[0][1], day=1,
                               hour=0, minute=0, second=0, microsecond=0)
        por_mes = {(d.year, d.month): n for d, n in inters.filter(fecha__gte=inicio)
                   .annotate(mes=TruncMonth('fecha')).values_list('mes')
                   .annotate(n=Count('id')).order_by()}

        tipos = dict(Interaction.TIPOS)
        con_empresa = clientes.exclude(company=None)
        return super().get_context_data(
            total_clientes=clientes.count(),
            total_empresas=con_empresa.values('company').distinct().count(),
            total_interacciones=inters.count(),
            ultimos_30=inters.filter(fecha__gte=ahora - timedelta(days=30)).count(),
            # series [etiqueta, n, clave] para ECharts (json_script en la plantilla)
            charts={
                'comercial': [(capfirst(u), n, pk) for u, pk, n in
                              clientes.values_list('comercial__username', 'comercial')
                              .annotate(n=Count('id')).order_by('-n', 'comercial__username')]
                             if user.is_superuser else None,
                'tipo': [(tipos[t], n, t) for t, n in
                         inters.values_list('tipo').annotate(n=Count('id')).order_by('-n')],
                'empresas': [(nombre, n, pk) for nombre, pk, n in
                             con_empresa.values_list('company__nombre', 'company')
                             .annotate(n=Count('id')).order_by('-n', 'company__nombre')[:5]],
                'mes': [(f'{m:02d}/{y}', por_mes.get((y, m), 0), f'{y}-{m:02d}') for y, m in meses],
            },
            **kwargs,
        )


# --- Empresas ---------------------------------------------------------------

class CompanyListView(LoginRequiredMixin, ListView):
    def get_queryset(self):
        return Company.objects.annotate(n_clients=Count('clients'))


class CompanyFormMixin(FormularioMixin, LoginRequiredMixin):
    model = Company
    fields = ['nombre', 'sector', 'web']
    success_url = reverse_lazy('company_list')


class CompanyCreateView(CompanyFormMixin, CreateView):
    titulo = 'Nueva empresa'
    success_message = 'Empresa creada.'


class EmpresasEditablesMixin:
    """Un comercial solo edita/borra empresas sin clientes de otros comerciales."""
    def get_queryset(self):
        qs = Company.objects.all()
        if self.request.user.is_superuser:
            return qs
        ajenos = Client.objects.exclude(comercial=self.request.user).exclude(company=None)
        return qs.exclude(pk__in=ajenos.values('company'))


class CompanyUpdateView(EmpresasEditablesMixin, CompanyFormMixin, UpdateView):
    titulo = 'Editar empresa'
    success_message = 'Empresa actualizada.'


class CompanyDeleteView(EmpresasEditablesMixin, BorrarMixin, LoginRequiredMixin, DeleteView):
    success_url = reverse_lazy('company_list')
