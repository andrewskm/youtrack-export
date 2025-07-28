"""
YouTrack Export Console Application
Main entry point for the application.
"""
import sys

import questionary
from rich import print
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from src.youtrack_export.client import YouTrackClient
from src.youtrack_export.exceptions import AuthenticationError, YouTrackError
from src.youtrack_export.export import Export

console = Console()


def main():
    """Step into the application."""

    console.print(Markdown('# YouTrack Export', style='bold #0EB0F2'), style='bold #FF318C')

    try:
        # Initialize client (will prompt for credentials if needed)
        console.print('Initializing YouTrack client...', style='dim')
        client = YouTrackClient()

        # Get current user
        user = client.get_current_user()
        print(f'[bold]Connected as:[/bold] [green]{user.get('name', 'Unknown')}[/green]')

        while True:
            console.print(Markdown('***'))
            action: str = questionary.select(
                'What would you like to do?',
                choices=[
                    '1. List my projects',
                    '2. Export projects',
                    '3. Exit'
                ]).ask()

            if action and action.startswith('1'):
                list_projects(client)
            elif action and action.startswith('2'):
                init_export_projects(client)
            else:
                print('[bold red]Goodbye![/bold red]')
                sys.exit()

    except AuthenticationError as e:
        console.print(f'Authentication Error:', style='red')
        console.print(e)
        sys.exit(1)
    except YouTrackError as e:
        console.print(f'YouTrack Error:', style='red')
        console.print(e)
        sys.exit(1)
    except KeyboardInterrupt:
        console.print('Application cancelled by user.', style='red')
        sys.exit(1)
    except Exception as e:
        console.print(f'Unexpected error:', style='red')
        console.print(e)
        sys.exit(1)


def list_projects(client: YouTrackClient) -> None:
    """
    List all the current user's projects in a table.
    Args:
        client (YouTrackClient): YouTrackClient instance.
    """
    console.print('Listing projects... \n', style='dim')
    projects = client.get_projects()

    print(f'You are associated to [green]{len(projects)}[/green] projects.')
    console.print(Markdown('*Note: only active projects are exportable*'), style='dim')

    table = Table()
    table.add_column('ID', style='cyan')
    table.add_column('Name')
    table.add_column('Active', style='#D1711D')
    table.add_column('Description', style='dim')

    for project in projects:
        table.add_row(project.get('id', 'Unknown'), project.get('name', 'Unknown'), '[green]Yes[/green]' if not project.get('archived') else '[dim]No[/dim]', project.get('description'))

    console.print(table)


def init_export_projects(client: YouTrackClient) -> None:
    """
    Setup what the user wants to export and from which projects.
    Args:
        client (YouTrackClient): YouTrackClient instance.
    """
    action: str = questionary.select(
        'What active projects would you like to export?',
        choices=[
            '1. Everything',
            '2. Specific projects',
            '<< Back'
        ],
        qmark='🗃️'
    ).ask()

    # back
    if not action or action.startswith('<<'):
        return

    projects: list[str] = [f'{p.get('name')} | ID:{p.get('id')}' for p in client.get_projects() if p.get('archived') is not True]
    if action.startswith('2'):
        # User selects the projects and the id is parsed out of the selected strings.
        # Don't list archived projects in the choices since we can't get all data from the API.
        projects: list[str] = questionary.checkbox(
            'Select the projects would you like to export:',
            choices=projects,
            qmark='✔️'
        ).ask()

    if len(projects) == 0:
        console.print('No projects were selected.', style='red')
        return

    # What data does the user want to export from the api.
    export_items: list[str] = questionary.checkbox(
        f'What would you like to export from these {len(projects)} projects?',
        choices=[
            'Unresolved Issues',
            'Resolved Issues',
            'Comments',
            'Attachments',
        ],
        qmark='✔️'
    ).ask()

    if len(export_items) == 0:
        console.print('No export items were selected.', style='red')
        return

    # Send selected projects and export items to an export class.
    Export(client, projects, export_items)


if __name__ == "__main__":
    main()
