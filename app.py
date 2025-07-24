"""
YouTrack Export Console Application
Main entry point for the application.
"""
import sys
import questionary

from src.youtrack_export.client import YouTrackClient
from src.youtrack_export.exceptions import AuthenticationError, YouTrackError
from src.youtrack_export.export import Export


def main():
    """Step into the application."""
    print('YouTrack Export')
    print('=' * 30)

    try:
        # Initialize client (will prompt for credentials if needed)
        print('Initializing YouTrack client...')
        client = YouTrackClient()

        # Get current user
        user = client.get_current_user()
        print(f'Connected as: {user.get('name', 'Unknown')}')

        while True:
            action: str = questionary.select(
                'What would you like to do?',
                choices=[
                    '1. List my projects',
                    '2. Export projects',
                    '3. Exit'
                ]).ask()

            if action.startswith('1'):
                list_projects(client)
            elif action.startswith('2'):
                init_export_projects(client)
            else:
                print('Goodbye!')
                sys.exit()

    except AuthenticationError as e:
        print(f'Authentication Error: {e}')
        sys.exit(1)
    except YouTrackError as e:
        print(f'YouTrack Error: {e}')
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nApplication cancelled by user.')
        sys.exit(1)
    except Exception as e:
        print(f'Unexpected error: {e}')
        sys.exit(1)


def list_projects(client: YouTrackClient) -> None:
    """List all the current user's projects."""
    print('Listing projects...')
    projects = client.get_projects()

    print(f'\nYou are associated to {len(projects)} projects:')
    for project in projects:
        print(f'  - {project.get('name', 'Unknown')} ({project.get('id', 'Unknown')}) {'(Archived)' if project.get('archived', None) is not None else ''}')


def init_export_projects(client: YouTrackClient) -> None:
    """Setup what the user wants to export and from which projects."""
    action: str = questionary.select(
        'What projects would you like to export?',
        choices=[
            '1. Everything',
            '2. Specific projects',
            '<< Back'
        ]).ask()

    projects: list[str] = []
    if action.startswith('1'):
        projects = [p.get('id') for p in client.get_projects()]
    elif action.startswith('2'):
        """User selects the projects and the id is parsed out of the selected strings."""
        choices: list[str] = [f'{p.get('name')} | ID:{p.get('id')}' for p in client.get_projects()]
        selected_projects: list[str] = questionary.checkbox(
            'Which projects would you like to export?',
            choices=choices
        ).ask()
        projects = [p.split('ID:')[1] for p in selected_projects]

    if len(projects) == 0:
        print('No projects were selected.')
        return

    """What data does the user want to export from the api."""
    what_to_export: list[str] = questionary.checkbox(
        f'What would you like to export from these {len(projects)} projects?',
        choices=[
            'Unresolved Issues',
            'Resolved Issues',
            'Comments',
            'Attachments',
        ]).ask()

    if len(what_to_export) == 0:
        print('No export items were selected.')
        return

    """todo: Send selected projects and export items to an export class."""
    Export(projects, what_to_export)

if __name__ == "__main__":
    main()
