from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Company(models.Model):
    nombre = models.CharField('nombre', max_length=150)
    sector = models.CharField('sector', max_length=100, blank=True)
    web = models.URLField('web', blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'

    def __str__(self):
        return self.nombre


class Client(models.Model):
    nombre = models.CharField('nombre', max_length=100)
    apellidos = models.CharField('apellidos', max_length=150, blank=True)
    email = models.EmailField('email')
    telefono = models.CharField('teléfono', max_length=30, blank=True)
    company = models.ForeignKey(
        Company, verbose_name='empresa', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='clients',
    )
    comercial = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='comercial',
        on_delete=models.PROTECT, related_name='clients',
    )
    creado = models.DateTimeField('creado', auto_now_add=True)

    class Meta:
        ordering = ['nombre', 'apellidos']
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'

    def __str__(self):
        return f'{self.nombre} {self.apellidos}'.strip()

    def get_absolute_url(self):
        return reverse('client_detail', args=[self.pk])


class Interaction(models.Model):
    TIPOS = [
        ('llamada', 'Llamada'),
        ('email', 'Email'),
        ('reunion', 'Reunión'),
        ('otro', 'Otro'),
    ]
    client = models.ForeignKey(
        Client, verbose_name='cliente', on_delete=models.CASCADE,
        related_name='interactions',
    )
    tipo = models.CharField('tipo', max_length=10, choices=TIPOS)
    fecha = models.DateTimeField('fecha', default=timezone.now)
    notas = models.TextField('notas', blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='usuario',
        on_delete=models.PROTECT, related_name='interactions',
    )

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'interacción'
        verbose_name_plural = 'interacciones'

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.client} ({self.fecha:%d/%m/%Y})'
