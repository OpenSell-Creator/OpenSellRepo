from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
import os
import shutil
from pathlib import Path

class Command(BaseCommand):
    help = 'Compress CSS and JavaScript assets for production'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force compression even in DEBUG mode',
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean compressed files before compression',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('Starting asset compression...'))

        # Check if compression should run
        if settings.DEBUG and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    'Compression is disabled in DEBUG mode. Use --force to override.'
                )
            )
            return

        # Clean compressed files if requested
        if options['clean']:
            self.clean_compressed_files()

        # Collect static files first
        self.stdout.write('Collecting static files...')
        call_command('collectstatic', '--noinput', verbosity=0)

        # Compress assets
        self.stdout.write('Compressing assets...')
        try:
            call_command('compress', '--force')
            self.stdout.write(
                self.style.SUCCESS('✓ Assets compressed successfully!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Compression failed: {str(e)}')
            )
            return

        # Show compression statistics
        self.show_compression_stats()

    def clean_compressed_files(self):
        """Clean existing compressed files"""
        self.stdout.write('Cleaning compressed files...')
        
        # Clean COMPRESS_ROOT directory
        compress_root = getattr(settings, 'COMPRESS_ROOT', settings.STATIC_ROOT)
        if compress_root:
            compressed_dir = os.path.join(compress_root, 'CACHE')
            if os.path.exists(compressed_dir):
                shutil.rmtree(compressed_dir)
                self.stdout.write(f'Cleaned {compressed_dir}')

    def show_compression_stats(self):
        """Show compression statistics"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('COMPRESSION STATISTICS')
        self.stdout.write('='*50)

        # Count CSS and JS files
        static_root = Path(settings.STATIC_ROOT)
        
        if static_root.exists():
            css_files = list(static_root.glob('**/*.css'))
            js_files = list(static_root.glob('**/*.js'))
            
            # Count compressed files
            cache_dir = static_root / 'CACHE'
            compressed_css = list(cache_dir.glob('**/*.css')) if cache_dir.exists() else []
            compressed_js = list(cache_dir.glob('**/*.js')) if cache_dir.exists() else []
            
            self.stdout.write(f'Original CSS files: {len(css_files)}')
            self.stdout.write(f'Compressed CSS files: {len(compressed_css)}')
            self.stdout.write(f'Original JS files: {len(js_files)}')
            self.stdout.write(f'Compressed JS files: {len(compressed_js)}')
            
            # Calculate total sizes
            original_size = sum(f.stat().st_size for f in css_files + js_files)
            compressed_size = sum(f.stat().st_size for f in compressed_css + compressed_js)
            
            if compressed_size > 0:
                reduction = ((original_size - compressed_size) / original_size) * 100
                self.stdout.write(f'Original size: {self.format_bytes(original_size)}')
                self.stdout.write(f'Compressed size: {self.format_bytes(compressed_size)}')
                self.stdout.write(f'Size reduction: {reduction:.1f}%')
        
        self.stdout.write('='*50)

    def format_bytes(self, bytes_size):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"