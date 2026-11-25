from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Client, Company, Interaction


class CrmTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user('ana', password='x')
        cls.luis = User.objects.create_user('luis', password='x')
        acme = Company.objects.create(nombre='Acme')
        cls.c_ana = Client.objects.create(
            nombre='Pedro', apellidos='Gómez', email='pedro@mail.com',
            company=acme, comercial=cls.ana)
        cls.c_luis = Client.objects.create(
            nombre='Marta', email='marta@otra.com', comercial=cls.luis)

    def setUp(self):
        self.client.force_login(self.ana)

    def buscar(self, q):
        return self.client.get(reverse('client_list'), {'q': q}).context['object_list']

    def test_buscador(self):
        for q in ('Pedro', 'pedro@mail', 'acme'):
            self.assertEqual(list(self.buscar(q)), [self.c_ana])
        self.assertEqual(list(self.buscar('zzz')), [])

    def test_comercial_solo_ve_sus_clientes(self):
        self.assertEqual(list(self.buscar('')), [self.c_ana])
        r = self.client.get(reverse('client_detail', args=[self.c_luis.pk]))
        self.assertEqual(r.status_code, 404)

    def test_superuser_ve_todos(self):
        User.objects.create_superuser('admin', password='x')
        self.client.login(username='admin', password='x')
        self.assertEqual(len(self.buscar('')), 2)

    def test_paginas_cargan(self):
        pk = self.c_ana.pk
        for name, args in [
            ('client_list', []), ('client_create', []), ('client_detail', [pk]),
            ('client_update', [pk]), ('client_delete', [pk]),
            ('interaction_create', [pk]), ('company_list', []),
            ('company_create', []),
        ]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def exportar(self, **params):
        r = self.client.get(reverse('client_export'), params)
        return r, r.content.decode('utf-8-sig').splitlines()

    def test_exportar_csv_solo_clientes_propios(self):
        r, filas = self.exportar()
        self.assertTrue(r['Content-Type'].startswith('text/csv'))
        self.assertIn('clientes.csv', r['Content-Disposition'])
        self.assertTrue(r.content.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(len(filas), 2)  # cabecera + Pedro
        self.assertIn(';', filas[0])
        self.assertIn('Pedro', filas[1])
        self.assertNotIn('Marta', r.content.decode())

    def test_exportar_respeta_busqueda_y_superuser_ve_todo(self):
        self.assertEqual(len(self.exportar(q='zzz')[1]), 1)
        User.objects.create_superuser('admin', password='x')
        self.client.login(username='admin', password='x')
        self.assertEqual(len(self.exportar()[1]), 3)
        self.assertEqual(len(self.exportar(q='marta')[1]), 2)

    def test_exportar_escapa_formulas(self):
        Client.objects.create(nombre='=SUMA(1)', email='f@f.com', comercial=self.ana)
        self.assertIn("'=SUMA(1)", self.exportar()[0].content.decode('utf-8-sig'))

    def test_estadisticas(self):
        Interaction.objects.create(client=self.c_ana, tipo='llamada', usuario=self.ana)
        Interaction.objects.create(client=self.c_luis, tipo='email', usuario=self.luis)
        r = self.client.get(reverse('stats'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.context['total_clientes'], r.context['total_interacciones']), (1, 1))
        self.assertIsNone(r.context['charts']['comercial'])
        self.assertEqual(sum(n for _, n, _k in r.context['charts']['tipo']), 1)
        self.assertEqual(r.context['charts']['tipo'][0][2], 'llamada')
        self.assertEqual(r.context['charts']['empresas'][0][2], self.c_ana.company_id)
        self.assertRegex(r.context['charts']['mes'][-1][2], r'^\d{4}-\d{2}$')
        User.objects.create_superuser('admin', password='x')
        self.client.login(username='admin', password='x')
        r = self.client.get(reverse('stats'))
        self.assertEqual((r.context['total_clientes'], r.context['total_interacciones']), (2, 2))
        self.assertEqual(len(r.context['charts']['comercial']), 2)

    def test_exportar_y_estadisticas_piden_login(self):
        self.client.logout()
        for name in ('client_export', 'stats'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)

    def test_crear_cliente_asigna_comercial(self):
        self.client.post(reverse('client_create'), {
            'nombre': 'Nuevo', 'email': 'n@n.com'})
        self.assertEqual(Client.objects.get(nombre='Nuevo').comercial, self.ana)

    def test_crud_interaccion(self):
        url = reverse('interaction_create', args=[self.c_ana.pk])
        self.client.post(url, {
            'tipo': 'llamada', 'fecha': '2026-01-01 10:00', 'notas': 'Hola'})
        i = Interaction.objects.get()
        self.assertEqual((i.client, i.usuario), (self.c_ana, self.ana))
        self.client.post(reverse('interaction_update', args=[i.pk]), {
            'tipo': 'email', 'fecha': '2026-01-01 10:00', 'notas': 'Cambio'})
        i.refresh_from_db()
        self.assertEqual((i.tipo, i.notas), ('email', 'Cambio'))
        self.client.post(reverse('interaction_delete', args=[i.pk]))
        self.assertFalse(Interaction.objects.exists())

    def test_modal_ajax_devuelve_fragmento(self):
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        pk = self.c_ana.pk
        for name, args in [('client_create', []), ('client_update', [pk]), ('client_delete', [pk])]:
            url = reverse(name, args=args)
            r = self.client.get(url, **ajax)
            self.assertEqual(r.status_code, 200, name)
            self.assertNotContains(r, '<html')
            self.assertNotContains(r, 'folder-tabs')
            r = self.client.get(url)
            self.assertContains(r, '<html')
            self.assertContains(r, 'folder-tabs')

    def test_modal_post(self):
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        url = reverse('client_create')
        r = self.client.post(url, {'nombre': ''}, **ajax)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '<form')
        self.assertContains(r, 'errorlist')
        self.assertNotContains(r, '<html')
        r = self.client.post(url, {'nombre': 'Ajax', 'email': 'a@a.com'}, **ajax)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Client.objects.filter(nombre='Ajax').exists())
        r = self.client.post(reverse('client_delete', args=[self.c_ana.pk]), **ajax)
        self.assertEqual(r.status_code, 302)


class ListaFiltrosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user('ana', password='x')
        cls.luis = User.objects.create_user('luis', password='x')
        cls.admin = User.objects.create_superuser('admin', password='x')
        cls.acme = Company.objects.create(nombre='Acme')
        cls.zeta = Company.objects.create(nombre='Zeta')
        cls.a = Client.objects.create(nombre='Ana', email='a@a.com', company=cls.zeta, comercial=cls.ana)
        cls.b = Client.objects.create(nombre='Beto', email='b@a.com', company=cls.acme, comercial=cls.ana)
        cls.c = Client.objects.create(nombre='Carla', email='c@a.com', company=cls.acme, comercial=cls.luis)
        Interaction.objects.create(client=cls.a, tipo='llamada', usuario=cls.ana)
        Interaction.objects.create(client=cls.a, tipo='llamada', usuario=cls.ana)
        Interaction.objects.create(client=cls.b, tipo='email', usuario=cls.ana)

    def lista(self, user='ana', **params):
        self.client.force_login(User.objects.get(username=user))
        r = self.client.get(reverse('client_list'), params)
        return [c.nombre for c in r.context['object_list']], r

    def test_orden_lista_blanca(self):
        self.assertEqual(self.lista(orden='-nombre')[0], ['Beto', 'Ana'])
        self.assertEqual(self.lista(orden='empresa')[0], ['Beto', 'Ana'])
        self.assertEqual(self.lista(orden='-empresa')[0], ['Ana', 'Beto'])
        self.assertEqual(self.lista(orden='alta')[0], ['Ana', 'Beto'])
        self.assertEqual(self.lista(orden='; drop')[0], ['Ana', 'Beto'])
        r = self.lista(orden='-alta')[1]
        self.assertEqual(r.context['sort']['alta']['aria'], 'descending')
        self.assertContains(r, 'aria-sort="descending"')

    def test_filtros_y_permisos(self):
        self.assertEqual(self.lista(empresa=self.acme.pk)[0], ['Beto'])
        self.assertEqual(self.lista(empresa='abc')[0], ['Ana', 'Beto'])
        self.assertEqual(self.lista(empresa='9' * 30)[0], ['Ana', 'Beto'])
        # un comercial no puede ver ajenos por filtro, y comercial= se ignora
        self.assertEqual(self.lista(comercial=self.luis.pk)[0], ['Ana', 'Beto'])
        self.assertEqual(self.lista(empresa=self.acme.pk, q='carla')[0], [])
        n, r = self.lista('admin', comercial=self.luis.pk)
        self.assertEqual(n, ['Carla'])
        self.assertEqual(self.lista('admin', comercial=self.luis.pk, empresa=self.zeta.pk)[0], [])
        self.assertEqual([c.nombre for c in r.context['empresas']], ['Acme', 'Zeta'])
        r = self.lista('luis')[1]
        self.assertEqual([c.nombre for c in r.context['empresas']], ['Acme'])
        self.assertIsNone(self.lista()[1].context['comerciales'])

    def test_filtro_tipo_y_mes(self):
        self.assertEqual(self.lista(tipo='llamada')[0], ['Ana'])  # sin duplicados
        self.assertEqual(self.lista(tipo='email')[0], ['Beto'])
        self.assertEqual(self.lista(tipo='xx')[0], ['Ana', 'Beto'])
        mes = timezone.localtime().strftime('%Y-%m')
        self.assertEqual(self.lista(mes=mes)[0], ['Ana', 'Beto'])
        self.assertEqual(self.lista(mes='2001-01')[0], [])
        self.assertEqual(self.lista(mes='2026-13')[0], ['Ana', 'Beto'])
        self.assertEqual(self.lista(mes='0000-01')[0], ['Ana', 'Beto'])  # ignorado, sin 500
        self.assertEqual(self.lista(tipo='email', mes=mes)[0], ['Beto'])
        r = self.lista(tipo='llamada', mes=mes)[1]
        self.assertEqual(len(r.context['chips']), 2)
        self.assertContains(r, 'Limpiar filtros')

    def test_paginacion_y_exportacion_conservan_filtros(self):
        for i in range(12):
            Client.objects.create(nombre=f'Z{i:02d}', email='z@z.com', company=self.acme, comercial=self.ana)
        r = self.lista(empresa=self.acme.pk, orden='-nombre')[1]
        self.assertContains(r, 'empresa=%d&amp;orden=-nombre&amp;page=2' % self.acme.pk)
        self.assertContains(r, '/clientes/exportar/?empresa=%d&amp;orden=-nombre' % self.acme.pk)
        csv = self.client.get(reverse('client_export'), {'empresa': self.acme.pk, 'orden': '-nombre'}).content.decode('utf-8-sig')
        filas = csv.splitlines()
        self.assertEqual(len(filas), 14)
        self.assertTrue(filas[1].startswith('Z11'))
        csv = self.client.get(reverse('client_export'), {'tipo': 'email'}).content.decode('utf-8-sig')
        self.assertEqual(len(csv.splitlines()), 2)

    def test_detalle_agrupa_por_mes_y_empresa_cuenta_clientes(self):
        self.client.force_login(self.ana)
        r = self.client.get(reverse('client_detail', args=[self.a.pk]))
        self.assertEqual(r.context['iniciales'], 'A')
        self.assertEqual(sum(len(g['items']) for g in r.context['grupos']), 2)
        self.assertContains(r, 'quick-form')
        self.assertContains(r, 'tl-item')
        vacio = self.client.get(reverse('client_detail', args=[self.b.pk]))
        self.assertEqual(len(vacio.context['grupos']), 1)
        c = Client.objects.create(nombre='Sin', email='s@s.com', comercial=self.ana)
        r = self.client.get(reverse('client_detail', args=[c.pk]))
        self.assertContains(r, 'timeline-empty')
        self.assertContains(r, 'autofocus')
        self.client.force_login(self.ana)
        r = self.client.get(reverse('company_list'))
        self.assertContains(r, 'Los clientes quedan sin empresa.')

    def test_borrado_silencioso_con_cabecera(self):
        self.client.force_login(self.ana)
        r = self.client.post(reverse('client_delete', args=[self.b.pk]),
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_X_SILENT='1')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Client.objects.filter(pk=self.b.pk).exists())
        self.assertEqual(list(r.wsgi_request._messages), [])

    def test_pagina_fuera_de_rango_o_no_numerica(self):
        for _ in range(12):
            Client.objects.create(nombre='Z', email='z@z.com', comercial=self.ana)
        for page in ('999', 'abc'):
            n, r = self.lista(page=page)
            self.assertEqual(r.status_code, 200, page)
            self.assertEqual(r.context['page_obj'].number, 2 if page == '999' else 1)


class PermisosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user('ana', password='x')
        cls.luis = User.objects.create_user('luis', password='x')
        cls.c_luis = Client.objects.create(nombre='Marta', email='m@m.com', comercial=cls.luis)
        cls.i_luis = Interaction.objects.create(client=cls.c_luis, tipo='email', usuario=cls.luis)
        cls.mixta = Company.objects.create(nombre='Mixta')
        cls.propia = Company.objects.create(nombre='Propia')
        Client.objects.create(nombre='A', email='a@a.com', company=cls.mixta, comercial=cls.ana)
        Client.objects.create(nombre='B', email='b@a.com', company=cls.mixta, comercial=cls.luis)
        Client.objects.create(nombre='C', email='c@a.com', company=cls.propia, comercial=cls.ana)
        cls.vacia = Company.objects.create(nombre='Vacia')

    def setUp(self):
        self.client.force_login(self.ana)

    def test_interacciones_ajenas_404(self):
        datos = {'tipo': 'email', 'fecha': '2026-01-01 10:00', 'notas': 'x'}
        for name, arg in [('interaction_update', self.i_luis.pk), ('interaction_delete', self.i_luis.pk),
                          ('interaction_create', self.c_luis.pk)]:
            url = reverse(name, args=[arg])
            self.assertEqual(self.client.get(url).status_code, 404, name)
            self.assertEqual(self.client.post(url, datos).status_code, 404, name)
        self.assertEqual(Interaction.objects.count(), 1)
        self.i_luis.refresh_from_db()
        self.assertEqual(self.i_luis.notas, '')

    def test_empresa_con_clientes_ajenos_bloqueada(self):
        for name in ('company_update', 'company_delete'):
            url = reverse(name, args=[self.mixta.pk])
            self.assertEqual(self.client.get(url).status_code, 404, name)
            self.assertEqual(self.client.post(url, {'nombre': 'X'}).status_code, 404, name)
        self.assertEqual(Company.objects.get(pk=self.mixta.pk).nombre, 'Mixta')

    def test_empresa_sin_clientes_ajenos_permitida(self):
        for emp in (self.propia, self.vacia):
            url = reverse('company_update', args=[emp.pk])
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.post(url, {'nombre': 'Nueva'}).status_code, 302)
            self.assertEqual(Company.objects.get(pk=emp.pk).nombre, 'Nueva')
            self.assertEqual(self.client.post(reverse('company_delete', args=[emp.pk])).status_code, 302)
            self.assertFalse(Company.objects.filter(pk=emp.pk).exists())

    def test_superuser_edita_cualquier_empresa(self):
        User.objects.create_superuser('admin', password='x')
        self.client.login(username='admin', password='x')
        self.assertEqual(self.client.get(reverse('company_update', args=[self.mixta.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('company_delete', args=[self.mixta.pk])).status_code, 302)
