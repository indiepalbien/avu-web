from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from avuweb.main.models import UserProfile


class Command(BaseCommand):
    help = 'Create test users (5 socios and 2 empresas)'

    def handle(self, *args, **options):
        test_data = {
            'socios': [
                {
                    'email': 'socio1@test.com',
                    'password': 'test1234',
                    'full_name': 'Juan García',
                    'identity_number': '12.345.678-1',
                    'phone_number': '+598 9 1234 5678',
                    'address': 'Av. Principal 123, Montevideo',
                },
                {
                    'email': 'socio2@test.com',
                    'password': 'test1234',
                    'full_name': 'María López',
                    'identity_number': '12.345.678-2',
                    'phone_number': '+598 9 2345 6789',
                    'address': 'Calle Segunda 456, Montevideo',
                },
                {
                    'email': 'socio3@test.com',
                    'password': 'test1234',
                    'full_name': 'Carlos Rodríguez',
                    'identity_number': '12.345.678-3',
                    'phone_number': '+598 9 3456 7890',
                    'address': 'Calle Tercera 789, Montevideo',
                },
                {
                    'email': 'socio4@test.com',
                    'password': 'test1234',
                    'full_name': 'Ana Martínez',
                    'identity_number': '12.345.678-4',
                    'phone_number': '+598 9 4567 8901',
                    'address': 'Calle Cuarta 1011, Montevideo',
                },
                {
                    'email': 'socio5@test.com',
                    'password': 'test1234',
                    'full_name': 'Pedro Sánchez',
                    'identity_number': '12.345.678-5',
                    'phone_number': '+598 9 5678 9012',
                    'address': 'Calle Quinta 1213, Montevideo',
                },
            ],
            'empresas': [
                {
                    'email': 'empresa1@test.com',
                    'password': 'test1234',
                    'full_name': 'Tienda Verde SRL',
                    'rut': '12.345.678-1',
                    'address': 'Ruta 2 km 20, Canelones',
                },
                {
                    'email': 'empresa2@test.com',
                    'password': 'test1234',
                    'full_name': 'Restaurante Vegano UY',
                    'rut': '12.345.678-2',
                    'address': 'Bulevar Español 2500, Montevideo',
                },
            ],
        }

        created_count = 0
        skipped_count = 0

        # Create socios
        self.stdout.write(self.style.SUCCESS('\n=== Creando Socios ==='))
        for socio in test_data['socios']:
            if User.objects.filter(email=socio['email']).exists():
                self.stdout.write(
                    self.style.WARNING(f"⊘ Saltando: {socio['email']} (ya existe)")
                )
                skipped_count += 1
                continue

            user = User.objects.create_user(
                username=socio['email'],
                email=socio['email'],
                password=socio['password'],
            )
            UserProfile.objects.create(
                user=user,
                user_type='socio',
                full_name=socio['full_name'],
                identity_number=socio['identity_number'],
                phone_number=socio['phone_number'],
                address=socio['address'],
            )
            self.stdout.write(
                self.style.SUCCESS(f"✓ Creado: {socio['full_name']} ({socio['email']})")
            )
            created_count += 1

        # Create empresas
        self.stdout.write(self.style.SUCCESS('\n=== Creando Empresas ==='))
        for empresa in test_data['empresas']:
            if User.objects.filter(email=empresa['email']).exists():
                self.stdout.write(
                    self.style.WARNING(f"⊘ Saltando: {empresa['email']} (ya existe)")
                )
                skipped_count += 1
                continue

            user = User.objects.create_user(
                username=empresa['email'],
                email=empresa['email'],
                password=empresa['password'],
            )
            UserProfile.objects.create(
                user=user,
                user_type='empresa',
                full_name=empresa['full_name'],
                rut=empresa['rut'],
                address=empresa['address'],
            )
            self.stdout.write(
                self.style.SUCCESS(f"✓ Creado: {empresa['full_name']} ({empresa['email']})")
            )
            created_count += 1

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n=== Resumen ==='))
        self.stdout.write(self.style.SUCCESS(f'Usuarios creados: {created_count}'))
        self.stdout.write(self.style.WARNING(f'Usuarios saltados: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS(f'Total: {created_count + skipped_count}'))

        self.stdout.write(self.style.SUCCESS('\n✓ Comando completado exitosamente\n'))
