import os
import random
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.models import Client, Company, Interaction

EMPRESAS = [
    ('Tecnologías Albor', 'Software', 'https://www.tecnologiasalbor.es'),
    ('Construcciones Valdés', 'Construcción', 'https://www.construccionesvaldes.es'),
    ('Bodegas Ribera Alta', 'Alimentación y bebidas', 'https://www.bodegasriberaalta.es'),
    ('Clínica Dental Sonrisa', 'Salud', 'https://www.clinicasonrisa.es'),
    ('Logística Mediterránea', 'Transporte', 'https://www.logisticamediterranea.es'),
    ('Estudio Arquitectura Norte', 'Arquitectura', 'https://www.estudionorte.es'),
    ('Moda Urbana Iberia', 'Retail', 'https://www.modaurbanaiberia.es'),
    ('Asesoría Fiscal Peña', 'Servicios profesionales', 'https://www.asesoriapena.es'),
]

# (nombre, apellidos, índice de empresa o None)
CLIENTES = [
    ('Lucía', 'Fernández Ortega', 0), ('Carlos', 'Martín Gil', 0), ('Elena', 'Ruiz Navarro', 0),
    ('Javier', 'Sánchez Mora', 1), ('Pilar', 'Vidal Cano', 1), ('Andrés', 'Herrera Soto', 1),
    ('Raquel', 'Domínguez Prieto', 2), ('Miguel Ángel', 'Castro León', 2), ('Beatriz', 'Molina Iglesias', 2),
    ('Sergio', 'Ramos Cabello', 3), ('Cristina', 'Vega Marín', 3), ('Daniel', 'Gutiérrez Pons', 4),
    ('Nuria', 'Campos Aguilar', 4), ('Pablo', 'Serrano Lara', 4), ('Isabel', 'Romero Blanco', 5),
    ('Alberto', 'Núñez Crespo', 5), ('Marina', 'Flores Duran', 6), ('Hugo', 'Ibáñez Roca', 6),
    ('Laura', 'Peña Cordero', 7), ('Rubén', 'Santos Vallejo', 7), ('Teresa', 'Gallego Muñoz', None),
    ('Óscar', 'Lozano Barrera', None), ('Silvia', 'Cortés Rey', None), ('Fernando', 'Arias Montero', None),
    ('Patricia', 'Hidalgo Ferrer', None),
]

NOTAS = {
    'llamada': [
        'Llamada de seguimiento sobre la propuesta enviada. Pide un par de días para consultarlo.',
        'Primer contacto telefónico. Interesado en conocer tarifas y plazos.',
        'Llamada para resolver dudas de facturación. Queda resuelto.',
        'No contesta, se deja mensaje de voz.',
        'Confirma que renovará el contrato el próximo trimestre.',
        'Consulta por una incidencia con el último pedido. Se escala a soporte.',
        'Solicita presupuesto ampliado para otra sede.',
    ],
    'email': [
        'Envío de presupuesto detallado con tres opciones.',
        'Respuesta a su consulta sobre condiciones de pago.',
        'Se envía documentación y casos de éxito.',
        'Recordatorio de reunión de la próxima semana.',
        'Agradece la propuesta y pide una versión con descuento por volumen.',
        'Envío de contrato para revisión y firma.',
        'Comparte el calendario de entregas acordado.',
    ],
    'reunion': [
        'Reunión en sus oficinas. Presentación de la solución y demo.',
        'Videollamada de kickoff con el equipo del cliente.',
        'Comida de negocios para estrechar la relación comercial.',
        'Reunión de revisión trimestral. Satisfecho con el servicio.',
        'Visita a sus instalaciones para valorar necesidades.',
        'Reunión de negociación de precios. Quedan puntos pendientes.',
    ],
    'otro': [
        'Coincidencia en feria sectorial, intercambio de tarjetas.',
        'Se envía regalo corporativo de fin de año.',
        'Contacto por LinkedIn, acepta la invitación.',
        'Asistió al webinar de presentación de producto.',
    ],
}

SIN_ACENTOS = str.maketrans('áéíóúñ', 'aeioun')


class Command(BaseCommand):
    help = 'Rellena la base de datos con datos de demo (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Borra Interaction, Client y Company antes de recrear (no usuarios).')

    def handle(self, *args, **opts):
        if opts['reset']:
            Interaction.objects.all().delete()
            Client.objects.all().delete()
            Company.objects.all().delete()

        User = get_user_model()
        demo_pwd = os.environ.get('DEMO_PASSWORD')  # despliegue (Render): contraseña común, sin credenciales-dev.txt
        if demo_pwd:
            admin, created = User.objects.get_or_create(
                username='admin', defaults={'is_staff': True, 'is_superuser': True})
            if created:
                admin.set_password(demo_pwd)
                admin.save()
        comerciales, nuevas = [], []
        for username in ('marta', 'jorge'):
            user, created = User.objects.get_or_create(username=username, defaults={'is_staff': False})
            if created:
                pwd = demo_pwd or secrets.token_urlsafe(12)
                user.set_password(pwd)
                user.save()
                nuevas.append(f'usuario: {username} / password: {pwd}\n')
            comerciales.append(user)
        if nuevas and not demo_pwd:  # la contraseña solo existe al crearlos; no se reescribe en ejecuciones posteriores
            with open(Path(settings.BASE_DIR) / 'credenciales-dev.txt', 'a', encoding='utf-8') as f:
                f.write('\n' +''.join(nuevas))

        empresas = [Company.objects.get_or_create(nombre=n, defaults={'sector': s, 'web': w})[0]
                    for n, s, w in EMPRESAS]

        clientes = []
        for i, (nombre, apellidos, emp) in enumerate(CLIENTES):
            dominio = empresas[emp].web.split('www.')[1] if emp is not None else 'gmail.com'
            email = f"{nombre.split()[0].lower()}.{apellidos.split()[0].lower()}@{dominio}".translate(SIN_ACENTOS)
            cliente, _ = Client.objects.get_or_create(email=email, defaults={
                'nombre': nombre, 'apellidos': apellidos,
                'telefono': f'+34 6{(i * 37) % 90 + 10:02d} {(i * 211) % 900 + 100:03d} {(i * 523) % 900 + 100:03d}',
                'company': empresas[emp] if emp is not None else None,
                'comercial': comerciales[i % 2],
            })
            clientes.append(cliente)

        rng = random.Random(42)  # determinista: mismas claves (cliente, tipo, notas) en cada ejecución
        ahora = timezone.now()
        vistos = set()
        while len(vistos) < 60:
            cliente = rng.choice(clientes)
            tipo = rng.choice(list(NOTAS))
            notas = rng.choice(NOTAS[tipo])
            fecha = ahora - timedelta(days=rng.randint(0, 90), hours=rng.randint(0, 8), minutes=rng.randint(0, 59))
            if (cliente.pk, tipo, notas) in vistos:
                continue
            vistos.add((cliente.pk, tipo, notas))
            Interaction.objects.get_or_create(
                client=cliente, tipo=tipo, notas=notas,
                defaults={'fecha': fecha, 'usuario': cliente.comercial},
            )

        self.stdout.write(f'Empresas: {Company.objects.count()}, clientes: {Client.objects.count()}, '
                          f'interacciones: {Interaction.objects.count()}')
