# php-dev — PHP Development Skill

## Frameworks
- **Laravel:** `composer create-project laravel/laravel project-name`
- **Symfony:** `composer create-project symfony/skeleton project-name`
- **PHP Vanilla:** Servir con `php -S localhost:8000`

## Comandos Útiles
- `php artisan serve` — Servidor de desarrollo Laravel
- `php artisan make:model ModelName -m` — Modelo + migración
- `php artisan make:controller ControllerName --resource`
- `php artisan migrate` — Ejecutar migraciones
- `php artisan tinker` — REPL interactivo (Laravel)
- `composer dump-autoload` — Regenerar autoload

## Testing
- PHPUnit: `vendor/bin/phpunit` o `php artisan test`
- Pest: `vendor/bin/pest`

## Buenas Prácticas
- PSR-4 autoloading
- Validación en Form Requests (Laravel)
- Eloquent ORM para queries (Laravel)
- Prepared statements en PHP vanilla (seguridad)
- .env para configuración sensible
