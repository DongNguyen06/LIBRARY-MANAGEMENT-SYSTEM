"""Automatic template updater for Blueprint refactoring.

This script automatically updates all url_for() calls in Jinja2 templates
to use the new blueprint structure.

Usage:
    python update_templates.py [--dry-run] [--backup]

Options:
    --dry-run: Show what would be changed without modifying files
    --backup: Create .bak files before modifying
"""
import argparse
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple


# ==================== Route Mapping Configuration ====================

# Define all route mappings: old_route -> (blueprint, new_route)
ROUTE_MAPPINGS: Dict[str, Tuple[str, str]] = {
    # Authentication routes
    'login': ('auth', 'login'),
    'register': ('auth', 'register'),
    'logout': ('auth', 'logout'),
    'forgot_password': ('auth', 'forgot_password'),
    
    # Main/Public routes
    'home': ('main', 'home'),
    'search': ('main', 'search'),
    'book_detail': ('main', 'book_detail'),
    'chat': ('main', 'chat'),
    
    # User routes
    'user_dashboard': ('user', 'dashboard'),
    'dashboard': ('user', 'dashboard'),  # Alias
    'profile': ('user', 'profile'),
    'borrowed_books': ('user', 'borrowed_books'),
    'user_reservations': ('user', 'reservations'),
    'reservations': ('user', 'reservations'),  # Alias
    'favorites': ('user', 'favorites'),
    'notifications': ('user', 'notifications'),
    'pay_fine': ('user', 'pay_fine'),
    
    # Staff routes
    'staff_dashboard': ('staff', 'dashboard'),
    'staff_approve_borrow': ('staff', 'approve_borrow'),
    'staff_reject_borrow': ('staff', 'reject_borrow'),
    'staff_process_borrow': ('staff', 'process_borrow'),
    'staff_process_return': ('staff', 'process_return'),
    'staff_edit_book': ('staff', 'edit_book'),
    'staff_send_notifications': ('staff', 'send_notifications'),
    
    # Admin routes
    'admin_dashboard': ('admin', 'dashboard'),
    'admin_save_config': ('admin', 'save_config'),
    'admin_clear_logs': ('admin', 'clear_logs'),
    'admin_export_logs': ('admin', 'export_logs'),
    'admin_send_notifications': ('admin', 'send_notifications'),
    
    # API routes
    'api_get_users': ('api', 'get_users'),
    'api_get_books': ('api', 'get_books'),
    'api_borrow_book': ('api', 'borrow_book'),
    'reserve_book': ('api', 'reserve_book'),
    'api_cancel_borrow': ('api', 'cancel_borrow'),
    'cancel_reservation': ('api', 'cancel_reservation'),
    'api_renew_book': ('api', 'renew_book'),
    'api_manage_favorite': ('api', 'manage_favorite'),
    'api_get_notifications': ('api', 'get_notifications'),
    'api_send_notification': ('api', 'send_notification'),
    'api_read_notification': ('api', 'read_notification'),
    'api_read_all_notifications': ('api', 'read_all_notifications'),
    'api_delete_notification': ('api', 'delete_notification'),
    'api_chat_staff': ('api', 'get_staff'),
    'api_chat_conversations': ('api', 'get_conversations'),
    'api_chat_messages': ('api', 'get_messages'),
    'api_chat_unread': ('api', 'get_unread_count'),
    'submit_review': ('api', 'submit_review'),
    'edit_review': ('api', 'edit_review'),
    'delete_review': ('api', 'delete_review'),
}


class TemplateUpdater:
    """Updates Jinja2 templates with new Blueprint url_for() syntax."""
    
    def __init__(self, templates_dir: str, dry_run: bool = False, 
                 backup: bool = False):
        """Initialize the template updater.
        
        Args:
            templates_dir: Path to templates directory.
            dry_run: If True, show changes without modifying files.
            backup: If True, create .bak files before modifying.
        """
        self.templates_dir = Path(templates_dir)
        self.dry_run = dry_run
        self.backup = backup
        self.stats = {
            'files_processed': 0,
            'files_modified': 0,
            'replacements_made': 0,
            'errors': []
        }
    
    def find_template_files(self) -> List[Path]:
        """Find all Jinja2 template files.
        
        Returns:
            List of template file paths.
        """
        template_files = []
        for ext in ['*.html', '*.jinja2', '*.j2']:
            template_files.extend(self.templates_dir.rglob(ext))
        return template_files
    
    def update_url_for(self, content: str) -> Tuple[str, int]:
        """Update all url_for() calls in content.
        
        Args:
            content: Template file content.
            
        Returns:
            Tuple of (updated_content, num_replacements).
        """
        updated_content = content
        replacements = 0
        
        # Flask's built-in routes that should NOT be updated
        flask_builtin_routes = ['static', '_static', 'send_static_file']
        
        # Pattern to match url_for('route_name', ...)
        # Handles both single and double quotes
        patterns = [
            r"url_for\(\s*['\"]([^'\"]+)['\"]",  # Basic pattern
            r"url_for\(\s*['\"]([^'\"]+)['\"]([^)]*)\)",  # With parameters
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, updated_content)
            
            for match in matches:
                old_route = match.group(1)
                
                # Skip Flask built-in routes
                if old_route in flask_builtin_routes:
                    continue
                
                # Check if route needs updating
                if old_route in ROUTE_MAPPINGS:
                    blueprint, new_route = ROUTE_MAPPINGS[old_route]
                    new_url_for = f"{blueprint}.{new_route}"
                    
                    # Replace the route name
                    old_full = match.group(0)
                    new_full = old_full.replace(
                        f"'{old_route}'", 
                        f"'{new_url_for}'"
                    ).replace(
                        f'"{old_route}"',
                        f'"{new_url_for}"'
                    )
                    
                    updated_content = updated_content.replace(
                        old_full, 
                        new_full, 
                        1  # Replace only this occurrence
                    )
                    replacements += 1
        
        return updated_content, replacements
    
    def process_file(self, file_path: Path) -> None:
        """Process a single template file.
        
        Args:
            file_path: Path to template file.
        """
        try:
            # Read original content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Update content
            updated_content, num_replacements = self.update_url_for(
                original_content
            )
            
            self.stats['files_processed'] += 1
            
            if num_replacements > 0:
                self.stats['files_modified'] += 1
                self.stats['replacements_made'] += num_replacements
                
                relative_path = file_path.relative_to(self.templates_dir)
                print(f"✓ {relative_path}: {num_replacements} replacements")
                
                if not self.dry_run:
                    # Create backup if requested
                    if self.backup:
                        backup_path = file_path.with_suffix(
                            file_path.suffix + '.bak'
                        )
                        shutil.copy2(file_path, backup_path)
                        print(f"  → Backup: {backup_path.name}")
                    
                    # Write updated content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(updated_content)
            
        except Exception as e:
            error_msg = f"Error processing {file_path}: {str(e)}"
            self.stats['errors'].append(error_msg)
            print(f"✗ {error_msg}")
    
    def run(self) -> None:
        """Run the template updater."""
        print("=" * 70)
        print("Template Updater - Blueprint Refactoring")
        print("=" * 70)
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No files will be modified\n")
        elif self.backup:
            print("💾 BACKUP MODE - .bak files will be created\n")
        else:
            print("⚠️  LIVE MODE - Files will be modified in place\n")
        
        # Find all template files
        template_files = self.find_template_files()
        print(f"Found {len(template_files)} template files\n")
        
        # Process each file
        for file_path in template_files:
            self.process_file(file_path)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self) -> None:
        """Print summary statistics."""
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Files processed:     {self.stats['files_processed']}")
        print(f"Files modified:      {self.stats['files_modified']}")
        print(f"Total replacements:  {self.stats['replacements_made']}")
        
        if self.stats['errors']:
            print(f"\n⚠️  Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                print(f"  - {error}")
        
        if self.dry_run:
            print("\n💡 This was a dry run. Run without --dry-run to apply changes.")
        elif self.stats['files_modified'] > 0:
            print("\n✅ Templates updated successfully!")
            if self.backup:
                print("📁 Backup files (.bak) created for modified files.")
        else:
            print("\n✓ No changes needed - templates are up to date!")


def create_mapping_report(output_file: str = 'route_mappings.txt') -> None:
    """Create a report of all route mappings.
    
    Args:
        output_file: Path to output report file.
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Route Mapping Reference\n")
        f.write("=" * 70 + "\n\n")
        
        # Group by blueprint
        by_blueprint: Dict[str, List[Tuple[str, str]]] = {}
        for old_route, (blueprint, new_route) in ROUTE_MAPPINGS.items():
            if blueprint not in by_blueprint:
                by_blueprint[blueprint] = []
            by_blueprint[blueprint].append((old_route, new_route))
        
        # Write grouped mappings
        for blueprint in sorted(by_blueprint.keys()):
            f.write(f"\n{blueprint.upper()} Blueprint\n")
            f.write("-" * 70 + "\n")
            
            for old_route, new_route in sorted(by_blueprint[blueprint]):
                old_call = f"url_for('{old_route}')"
                new_call = f"url_for('{blueprint}.{new_route}')"
                f.write(f"{old_call:40} → {new_call}\n")
    
    print(f"\n📄 Route mapping report saved to: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Update Jinja2 templates for Blueprint refactoring',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (show changes without modifying files)
  python update_templates.py --dry-run
  
  # Update with backup
  python update_templates.py --backup
  
  # Update in place (no backup)
  python update_templates.py
  
  # Generate mapping report
  python update_templates.py --report-only
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create .bak files before modifying'
    )
    
    parser.add_argument(
        '--templates-dir',
        type=str,
        default=str(Path(__file__).parent / 'templates'),
        help='Path to templates directory (default: library_python/templates)'
    )
    
    parser.add_argument(
        '--report-only',
        action='store_true',
        help='Only generate route mapping report and exit'
    )
    
    args = parser.parse_args()
    
    # Generate report if requested
    if args.report_only:
        create_mapping_report()
        return
    
    # Check if templates directory exists
    templates_path = Path(args.templates_dir)
    if not templates_path.exists():
        print(f"❌ Error: Templates directory not found: {templates_path}")
        print("   Use --templates-dir to specify the correct path")
        return
    
    # Confirm before running in live mode
    if not args.dry_run and not args.backup:
        print("⚠️  WARNING: This will modify template files in place!")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
    
    # Run the updater
    updater = TemplateUpdater(
        templates_dir=str(templates_path),
        dry_run=args.dry_run,
        backup=args.backup
    )
    updater.run()
    
    # Generate mapping report
    if not args.dry_run:
        create_mapping_report()


if __name__ == '__main__':
    main()