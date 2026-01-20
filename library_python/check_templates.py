"""Template route checker for Blueprint refactoring.

This script scans all templates to find url_for() calls and reports:
- Which routes are already using blueprint syntax
- Which routes need to be updated
- Which routes are not in the mapping (potential issues)

Usage:
    python check_templates.py [--templates-dir DIR]
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Import route mappings from update script
# In real use, you'd import from update_templates.py
ROUTE_MAPPINGS = {
    'login': ('auth', 'login'),
    'register': ('auth', 'register'),
    'logout': ('auth', 'logout'),
    'forgot_password': ('auth', 'forgot_password'),
    'home': ('main', 'home'),
    'search': ('main', 'search'),
    'book_detail': ('main', 'book_detail'),
    'chat': ('main', 'chat'),
    'user_dashboard': ('user', 'dashboard'),
    'dashboard': ('user', 'dashboard'),
    'profile': ('user', 'profile'),
    'borrowed_books': ('user', 'borrowed_books'),
    'user_reservations': ('user', 'reservations'),
    'reservations': ('user', 'reservations'),
    'favorites': ('user', 'favorites'),
    'notifications': ('user', 'notifications'),
    'pay_fine': ('user', 'pay_fine'),
    'staff_dashboard': ('staff', 'dashboard'),
    'staff_approve_borrow': ('staff', 'approve_borrow'),
    'staff_reject_borrow': ('staff', 'reject_borrow'),
    'staff_process_borrow': ('staff', 'process_borrow'),
    'staff_process_return': ('staff', 'process_return'),
    'staff_edit_book': ('staff', 'edit_book'),
    'staff_send_notifications': ('staff', 'send_notifications'),
    'admin_dashboard': ('admin', 'dashboard'),
    'admin_save_config': ('admin', 'save_config'),
    'admin_clear_logs': ('admin', 'clear_logs'),
    'admin_export_logs': ('admin', 'export_logs'),
    'admin_send_notifications': ('admin', 'send_notifications'),
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


class TemplateChecker:
    """Checks templates for url_for() usage and migration status."""
    
    def __init__(self, templates_dir: str):
        """Initialize the checker.
        
        Args:
            templates_dir: Path to templates directory.
        """
        self.templates_dir = Path(templates_dir)
        self.results = {
            'already_updated': defaultdict(list),  # blueprint.route -> [files]
            'needs_update': defaultdict(list),     # old_route -> [files]
            'unmapped': defaultdict(list),         # route -> [files]
            'total_files': 0,
            'total_url_for_calls': 0
        }
    
    def find_template_files(self) -> List[Path]:
        """Find all template files.
        
        Returns:
            List of template file paths.
        """
        template_files = []
        for ext in ['*.html', '*.jinja2', '*.j2']:
            template_files.extend(self.templates_dir.rglob(ext))
        return template_files
    
    def extract_url_for_calls(self, content: str) -> List[str]:
        """Extract all url_for() route names from content.
        
        Args:
            content: Template content.
            
        Returns:
            List of route names found in url_for() calls.
        """
        # Pattern to match url_for('route_name') or url_for("route_name")
        pattern = r"url_for\(\s*['\"]([^'\"]+)['\"]"
        matches = re.findall(pattern, content)
        return matches
    
    def categorize_route(self, route: str, file_path: Path) -> None:
        """Categorize a route as updated, needs update, or unmapped.
        
        Args:
            route: Route name from url_for().
            file_path: Path to template file.
        """
        relative_path = str(file_path.relative_to(self.templates_dir))
        
        # Check if already using blueprint syntax (contains a dot)
        if '.' in route:
            self.results['already_updated'][route].append(relative_path)
        
        # Check if in mapping (needs update)
        elif route in ROUTE_MAPPINGS:
            self.results['needs_update'][route].append(relative_path)
        
        # Unknown route (not in mapping)
        else:
            self.results['unmapped'][route].append(relative_path)
    
    def check_file(self, file_path: Path) -> None:
        """Check a single template file.
        
        Args:
            file_path: Path to template file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            routes = self.extract_url_for_calls(content)
            self.results['total_url_for_calls'] += len(routes)
            
            for route in routes:
                self.categorize_route(route, file_path)
                
        except Exception as e:
            print(f"⚠️  Error reading {file_path}: {e}")
    
    def run(self) -> None:
        """Run the checker and print results."""
        print("=" * 70)
        print("Template Route Checker - Blueprint Migration Status")
        print("=" * 70 + "\n")
        
        # Find and process all templates
        template_files = self.find_template_files()
        self.results['total_files'] = len(template_files)
        
        print(f"Scanning {len(template_files)} template files...\n")
        
        for file_path in template_files:
            self.check_file(file_path)
        
        # Print results
        self.print_results()
    
    def print_results(self) -> None:
        """Print detailed results."""
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        
        # Summary statistics
        total_routes = (
            len(self.results['already_updated']) +
            len(self.results['needs_update']) +
            len(self.results['unmapped'])
        )
        
        print(f"\nTotal files scanned:       {self.results['total_files']}")
        print(f"Total url_for() calls:     {self.results['total_url_for_calls']}")
        print(f"Unique routes found:       {total_routes}")
        
        # Already updated (using blueprint syntax)
        if self.results['already_updated']:
            print(f"\n✅ ALREADY UPDATED ({len(self.results['already_updated'])} routes)")
            print("-" * 70)
            for route in sorted(self.results['already_updated'].keys()):
                files = self.results['already_updated'][route]
                print(f"  {route}")
                print(f"    Used in {len(files)} file(s): {', '.join(files[:3])}")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")
        
        # Needs update
        if self.results['needs_update']:
            print(f"\n⚠️  NEEDS UPDATE ({len(self.results['needs_update'])} routes)")
            print("-" * 70)
            for route in sorted(self.results['needs_update'].keys()):
                blueprint, new_route = ROUTE_MAPPINGS[route]
                files = self.results['needs_update'][route]
                print(f"  '{route}' → '{blueprint}.{new_route}'")
                print(f"    Found in {len(files)} file(s): {', '.join(files[:3])}")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")
        
        # Unmapped routes
        if self.results['unmapped']:
            print(f"\n❌ UNMAPPED ROUTES ({len(self.results['unmapped'])} routes)")
            print("-" * 70)
            print("  These routes were not found in the mapping configuration.")
            print("  They may need to be added to ROUTE_MAPPINGS.\n")
            
            for route in sorted(self.results['unmapped'].keys()):
                files = self.results['unmapped'][route]
                print(f"  '{route}'")
                print(f"    Found in {len(files)} file(s): {', '.join(files[:3])}")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")
        
        # Migration progress
        print("\n" + "=" * 70)
        print("MIGRATION PROGRESS")
        print("=" * 70)
        
        updated_count = len(self.results['already_updated'])
        needs_update_count = len(self.results['needs_update'])
        
        if total_routes > 0:
            progress = (updated_count / total_routes) * 100
            print(f"\nProgress: {updated_count}/{total_routes} routes updated ({progress:.1f}%)")
            
            if needs_update_count > 0:
                print(f"\n💡 Run update_templates.py to automatically update {needs_update_count} routes")
            else:
                print("\n✅ All known routes are using blueprint syntax!")
        
        if self.results['unmapped']:
            print(f"\n⚠️  Warning: {len(self.results['unmapped'])} unmapped routes found")
            print("   These may need to be added to ROUTE_MAPPINGS in update_templates.py")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Check template migration status for Blueprint refactoring'
    )
    
    # Tự động xác định đường dẫn templates mặc định: thư mục 'templates' nằm cùng cấp với script
    default_templates_dir = str((Path(__file__).parent / 'templates').resolve())
    parser.add_argument(
        '--templates-dir',
        type=str,
        default=default_templates_dir,
        help=f'Path to templates directory (default: {default_templates_dir})'
    )
    
    args = parser.parse_args()
    
    # Check if templates directory exists
    templates_path = Path(args.templates_dir)
    if not templates_path.exists():
        print(f"❌ Error: Templates directory not found: {templates_path}")
        return
    
    # Run the checker
    checker = TemplateChecker(str(templates_path))
    checker.run()


if __name__ == '__main__':
    main()