"""
Export management for the list of projects and items for each project.
"""
import asyncio
import json
import os
import shutil
from datetime import datetime

import aiohttp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TaskID
from slugify import slugify

from src.youtrack_export.client import YouTrackClient
from src.youtrack_export.exceptions import ExportError

console = Console()


class Export:
    __client_session: aiohttp.ClientSession = None
    __export_folder: str = 'exports'
    __issues_folder: str = 'issues'
    __attachments_folder: str = 'attachments'
    __metadata_filename: str = 'metadata.json'
    __batch_size: int = 100
    __items_per_page: int = 50
    __polling: dict[str, int] = {
        'max_attempts': 10,
        'delay': 2  # wait time for the next endpoint call
    }

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

                results = await asyncio.gather(*tasks, return_exceptions=True)

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

        try:
            progress.update(task, description='Fetching issues count...')
            # if the issues total is -1, the API is loading, so we need to wait for the count to be ready
            for attempt in range(1, self.__polling['max_attempts'] + 1):
                issues_total = await self.client.get_project_issue_count(self.__client_session, project, self.export_items)
                # if the return is None, the count does not exists
                if issues_total == None:
                    return 0
                
                if issues_total != -1:
                    progress.update(task, description=f'Issues count complete.', total=issues_total, completed=0)

                    return issues_total
                progress.update(task, description=f'Loading issues count...', advance=1, total=self.__polling['max_attempts'])
                await asyncio.sleep(self.__polling['delay'])

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

        parsed_issues: int = 0
        counts: dict[str, int] = {
            'resolved': 0,
            'unresolved': 0,
            'attachments': 0,
        }
        batch: int = 1

        # remove project issues directory in order to overwrite all batch files
        project_issues_folder = os.path.join(self.__get_project_folder(project, False), self.__issues_folder)
        if os.path.exists(project_issues_folder):
            try:
                shutil.rmtree(project_issues_folder)
            except Exception as e:
                raise ExportError(f'Failed to remove current project folder. {e}')

        export_attachments = 'Attachments' in self.export_items

        while True:
            try:
                issues = await self.client.get_issues(self.__client_session, project, self.export_items, skip=parsed_issues)

                # stop when the issues and batch list is empty
                if not issues:
                    break

                # loop through each issue and save
                for issue in issues:
                    # increment based on resolved field
                    if issue.get('resolved', False):
                        counts['resolved'] += 1
                    else:
                        counts['unresolved'] += 1

                    self._save_issue_to_disk(project, issue, batch)

                    # save issue attachments, if applicable
                    if export_attachments:
                        counts['attachments'] += self._save_project_attachments(project, issue)

                    parsed_issues += 1
                    progress.update(task, advance=1)

                    if parsed_issues % self.__batch_size == 0:
                        batch += 1
            except Exception as e:
                raise ExportError(f'Failed to export issues. {e}')

        self._save_project_metadata(project, counts)

        return parsed_issues

    def _save_issue_to_disk(self, project: dict[str, str], issue: dict, batch: int = 1) -> None:
        """
        Append and dump the issue to the batch file in the project folder.
        Args:
            project (dict[str, str]): Project dictionary with id and name.
            issues (dict): Issues list for the batch.
            batch (int): Current batch number
        """

        issues_file = os.path.join(self.__get_project_folder(project), self.__issues_folder, f'issues_batch_{batch}.json')
        try:
            os.makedirs(os.path.dirname(issues_file), exist_ok=True)
            try:
                # open the file if it exists, get existing data, extend that data, truncate and dump data back to the file
                with open(issues_file, 'r+', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []

                    if not data:
                        data = []

                    # clear the file before dumping
                    f.seek(0)
                    f.truncate()

                    data.append(issue)
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except FileNotFoundError:
                # create and dump the data into a new file when it doesn't exist
                with open(issues_file, 'w', encoding='utf-8') as f:
                    json.dump([issue], f, indent=2)
        except Exception as e:
            raise ExportError(f'Failed to write issue to batch file. {e}')

    def _save_project_attachments(self, project: dict[str, str], issue: dict) -> int:
        """
        Get the issue's attachments from the API and save to a file in the issue id folder of the project directory.
        Args:
            project (dict[str, str]): Project dictionary with id and name.
            issue (dict): Issue dictionary
        Returns:
            int: downloaded attachments count.
        """
        count = 0
        if not issue.get('attachments'):
            return count

        issue_id = issue.get('idReadable')
        attachments_folder = os.path.join(self.__get_project_folder(project), self.__attachments_folder, issue_id)
        os.makedirs(attachments_folder, exist_ok=True)

        # loop through each attachment and fetch and save the url content from the client
        for attachment in issue.get('attachments'):
            try:
                content = self.client.get_issue_attachment(attachment)
                # pluck the filename and extension so the file name can be trimmed if long
                filename, extension = os.path.splitext(attachment.get('name'))
                file_path = os.path.join(attachments_folder, f'{attachment.get('id')}_{filename[:100]}.{extension}')
                with open(file_path, 'wb') as f:
                    f.write(content)

                count += 1
            except Exception as e:
                raise ExportError(f'Failed to download attachment {attachment.get('name')} for issue {issue_id}. {e}')

        return count

    def _save_project_metadata(self, project: dict[str, str], counts: dict[str, int]) -> None:
        """
        Save a file to the project folder with details about the export.
        Args:
            project (dict[str, str]): Project dictionary with id and name.
            counts (dict[str, int]): Dictionary containing counts.
        """

        total = counts['resolved'] + counts['unresolved']

        metadata = {
            'export_date': datetime.now().isoformat(),
            'total_issues': total,
            'resolved_count': counts['resolved'],
            'unresolved_count': counts['unresolved'],
            'resolution_rate': round((counts['resolved'] / total if total else 0), 4),
            'total_attachments': counts['attachments'],
        }

        metadata_file = os.path.join(self.__get_project_folder(project), self.__metadata_filename)
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise ExportError(f'Failed to write metadata file. {e}')

    def __get_project_folder(self, project: dict[str, str], create: bool = True) -> str:
        """
        Create and get the export project folder full path.
        Args:
            project (dict[str, str]): Project dictionary with id and name.
            create (bool, optional): If True, create the project folder if it doesn't exist.
        Returns:
            str: Project folder full path.
        """

        project_folder = os.path.join(self.__export_folder, slugify(project.get('name')))

        # create the folder structure
        if create:
            os.makedirs(project_folder, exist_ok=True)

        return project_folder

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
