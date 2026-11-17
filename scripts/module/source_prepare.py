"""Read-only SVG/WebP checks; no image conversions or reference rewrites."""
from common.image_policy import inspect_image
def prepare_images(files, directory):
    inspected = 0
    for name, path in files.items():
        try:
            if inspect_image(name, path.read_bytes()):
                inspected += 1
        except (ValueError, OSError, EOFError) as error:
            raise ValueError(name + ': ' + str(error)) from error
    return dict(files), {'status':'passed', 'counts':{'inspected':inspected}, 'converted':0,
                         'conversions':[], 'issues':[], 'savedBytes':0}
