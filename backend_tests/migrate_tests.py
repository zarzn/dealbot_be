# Test migration script
import os
import shutil
from pathlib import Path

def migrate_test_file(source_path: str, target_path: str):
    """Migrate a test file to the new structure."""
    with open(source_path, 'r') as source:
        content = source.read()
        
    # Add new imports
    new_imports = '''
from utils.markers import depends_on
from utils.state import state_manager
from factories import UserFactory, GoalFactory, DealFactory
'''
    content = new_imports + content
    
    # Create target directory if not exists
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    with open(target_path, 'w') as target:
        target.write(content)

def main():
    # Define test mappings
    mappings = {
        'test_models': 'core/test_models',
        'test_auth': 'core/test_auth',
        'test_redis': 'core/test_redis',
        'test_user': 'services/test_user',
        'test_goal': 'services/test_goal',
        'test_deal': 'services/test_deal',
        'test_token': 'services/test_token',
        'test_api': 'integration/test_api',
        'test_websocket': 'integration/test_websocket'
    }
    
    # Migrate each test file
    for source_dir, target_dir in mappings.items():
        source_path = Path(f'tests/{source_dir}')
        target_path = Path(f'backend_tests/{target_dir}')
        
        if source_path.exists():
            for test_file in source_path.glob('test_*.py'):
                migrate_test_file(
                    str(test_file),
                    str(target_path / test_file.name)
                )

if __name__ == '__main__':
    main()
