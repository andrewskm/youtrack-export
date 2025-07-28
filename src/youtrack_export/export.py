"""
Export management for the list of projects and items for each project.
"""
import asyncio
import os
from typing import Any

import aiohttp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TaskID

from src.youtrack_export.client import YouTrackClient
from youtrack_export.exceptions import ExportError

console = Console()


class Export:
    __export_folder: str = 'export'
    __attachments_folder: str = 'attachments'
    __unresolved_folder: str = 'unresolved-issues'
    __resolved_folder: str = 'resolved-issues'
    __items_per_page: int = 50
    __tries: int = 3
    __client_session: aiohttp.ClientSession = None

    def __init__(self, client: YouTrackClient, projects: list[str], export_items: list[str]) -> None:
        """
        Initialize the Export class.
        Args:
            client (YouTrackClient): YouTrackClient instance.
            projects (list[str]): list of project names concatenated with ids.
            export_items (list[str]): list of export items.
        """
        self.client = client
        self.projects: list[dict[str, str]] = self._parse_projects(projects)
        self.export_items = export_items
        asyncio.run(self.export())

    async def export(self) -> None:
        """Start the async process for all projects and export items."""
        print()
        console.print(f'Processing export items ({', '.join(self.export_items)}) for [green]{len(self.projects)}[/green] project(s)...')

        # Make sure the export folder exists.
        if not os.path.exists(self.__export_folder):
            os.makedirs(self.__export_folder)

        # Loop through each project and display a progress task for each.
        async with aiohttp.ClientSession() as self.__client_session:
            with Progress(
                    SpinnerColumn(),
                    TextColumn('{task.fields[project]}'),
                    BarColumn(),
                    '[progress.percentage]{task.percentage:>3.0f}%',
                    TextColumn('({task.completed}/{task.total})'),
                    TimeElapsedColumn(),
                    TextColumn('[progress.description]{task.description}'),
                    console=console
            ) as progress:
                tasks = []
                for project in self.projects:
                    try:
                        task = progress.add_task('Starting export...', start=False, project=project.get('name'), total=0)

                        tasks.append(self._initiate_export(project, progress, task))
                    except Exception as e:
                        console.print(f'Error exporting {project.get('name')}: {e}', style='red')
                        break

                results = await asyncio.gather(*tasks)

        console.print('Export Complete!', style='bold green')

    async def _initiate_export(self, project: dict[str, str], progress: Progress, task: TaskID) -> TaskID:
        """
        Start the asynchronous export process.
        Args:
            project (dict[str, str]): Project dictionary with id and name.
            progress (Progress): Progress instance.
            task (TaskID): TaskID instance.
        """
        progress.start_task(task)

        try:
            # get the total issues count
            issues_total = await self._get_project_issues_count_with_polling(project, progress, task)

            # hide the progress if there are no issues
            if issues_total == 0:
                progress.update(task, visible=False)

            # start fetching the exportable data
            export_count = 0
            if issues_total is not None and issues_total > 0:
                export_count = await self._export_project(project, progress, task)

            # export has finished
            if export_count >= issues_total:
                progress.update(task, description='[green]Complete![/green]')
        except Exception as e:
            progress.update(task, description=f'[red]Error exporting: {e}[/red]')
        finally:
            progress.stop_task(task)

        return task

    async def _get_project_issues_count_with_polling(self, project: dict[str, str], progress: Progress, task: TaskID) -> int:
        """
        Get the project issues count by polling the endpoint until a validate result is returned.
        Args:
            project (dict[str, str]): Project dictionary with id and name.
            progress (Progress): Progress instance.
            task (TaskID): TaskID instance.
        Returns:
            int: project issues count.
        """
        max_attempts: int = 10
        delay: int = 2  # wait time for the next endpoint call

        try:
            progress.update(task, description='Fetching issues count...')
            # if the issues total is -1, the API is loading, so we need to wait for the count to be ready
            for attempt in range(1, max_attempts + 1):
                issues_total = await self.client.get_project_issue_count(self.__client_session, project, self.export_items)
                if issues_total != -1:
                    progress.update(task, description=f'Issues count complete.', total=issues_total, completed=0)

                    return issues_total
                progress.update(task, description=f'Loading issues count...', advance=1, total=max_attempts)
                await asyncio.sleep(delay)

            raise Exception('API did not return a valid issues count.')
        except Exception as e:
            raise ExportError(f'Failed to fetch issues count. {e}')

    async def _export_project(self, project: dict[str, str], progress: Progress, task: TaskID) -> int:
        """
        Asynchronously export the selected project with progress.
        Args:
            project (dict[str, str]): Project dictionary with id and name.
            progress (Progress): Progress instance.
            task (TaskID): TaskID instance.
        """
        progress.update(task, description='Exporting issues...')

        parsed_issues = 0
        batch = 1

        while True:
            try:
                issues = await self.client.get_issues(self.__client_session, project, self.export_items, skip=parsed_issues)

                # stop when the issues list is empty
                if not issues:
                    break

                # loop through each issue and save
                for issue in issues:
                    # save in batches (200 max issues per file?)
                    # todo - split resolved/unresolved here? batch for each type?
                    self._save_issues_to_disk(project, issue, batch)
                    # fetch and save attachments, if applicable
                    parsed_issues += 1
                    progress.update(task, advance=1)

                if parsed_issues % 100 == 0:
                    batch += 1

            except Exception as e:
                raise ExportError(f'Failed to get issues. {e}')

        return parsed_issues

    def _save_issues_to_disk(self, project: dict[str, str], lissues: list, batch: int = 1) -> tuple[list[Any], list[Any]]:
        """
        Parse the issues to a file in a project folder
        todo: figure best way to separate resolved/unresolved with batching separately
        """
        #     unresolved_full_path = f'{self.__export_folder}/{slugify(project_name)}/{self.__unresolved_folder}/issues_batch_{batch}.json '
        #     resolved_full_path = f'{self.__export_folder}/{slugify(project_name)}/{self.__resolved_folder}/issues_batch_{batch}.json '
        return [], []

    def _save_project_metadata(self, project, issues):
        """
        todo: save metadata to a file for project export details
        metadata = {
            'export_date': datetime.now().isoformat(),
            'total_issues': len(issues),
            'resolved_count': len(resolved_issues),
            'unresolved_count': len(unresolved_issues),
            'resolution_rate': len(resolved_issues) / len(issues) if issues else 0
        }
        """
        pass

    @staticmethod
    def _parse_projects(projects: list[str]) -> list[dict[str, str]]:
        """
        Parse the string of selected project strings names|ids into list of id, name dictionaries.
        Args:
            projects (list[str]): list of project names with ids.
        Returns:
            list[dict[str, str]]: list of Project dictionaries with id and name.
        """
        parsed_projects = []

        for project in projects:
            obj = {
                'id': project.split('| ID:')[1].strip(),
                'name': project.split('| ID:')[0].strip()
            }
            parsed_projects.append(obj)

        return parsed_projects
