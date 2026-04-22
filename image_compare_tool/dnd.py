import os

def collect_drop_paths(event):
    if not event.mimeData().hasUrls():
        return []
    paths = []
    for url in event.mimeData().urls():
        path = url.toLocalFile()
        if path and os.path.isfile(path):
            paths.append(path)
    return paths


def accept_drop_if_has_file(event):
    if collect_drop_paths(event):
        event.acceptProposedAction()
        return True
    event.ignore()
    return False


def handle_drop_event(event, compare_tab, **drop_options):
    paths = collect_drop_paths(event)
    if not paths or compare_tab is None:
        event.ignore()
        return

    if compare_tab.handle_dropped_paths(paths, **drop_options):
        event.acceptProposedAction()
        return

    event.ignore()
