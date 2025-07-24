class Export:
    def __init__(self, projects: list[str], export_items: list[str]) -> None:
        self.projects = projects
        self.export_items = export_items

        print(f'Processing export ({', '.join(self.export_items)}) export for {len(self.projects)} projects...')

    def export(self) -> None:
        """Start the async process for all projects and export items."""
        pass

    async def export_project(self) -> None:
        """Asynchronously export the selected project."""
        # get project unresolved issues
        # get project resolved issues
        # get project comments
        # get project attachments
        pass
