from ingestforge.core.registry import registry
from ingestforge.providers.destination.generic_rest import GenericRestDestination
from ingestforge.providers.destination.local_export import LocalExportDestination

registry.register_destination("local_export", LocalExportDestination)
registry.register_destination("generic_rest", GenericRestDestination)
