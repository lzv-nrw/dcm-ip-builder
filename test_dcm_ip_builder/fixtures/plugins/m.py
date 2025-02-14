from dcm_ip_builder.plugins.mapping import GenericMapper


class ExternalMapper(GenericMapper):
    def get_metadata(self, path, /, **kwargs):
        return kwargs
