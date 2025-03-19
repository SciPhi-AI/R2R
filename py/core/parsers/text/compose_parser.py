# type: ignore
from typing import AsyncGenerator, Dict, Any, List
import yaml
import re

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class DockerComposeParser(AsyncParser[str | bytes]):
    """A parser for Docker Compose files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

    async def ingest(
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest Docker Compose files and yield structured text representation.
        
        Extracts services, networks, volumes, and other configuration elements from
        Docker Compose files in a text format suitable for analysis.
        
        :param data: The Docker Compose file content to parse
        :param kwargs: Additional keyword arguments
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")
        
        # Process the Docker Compose content
        processed_text = self._process_compose_content(data)
        
        # Yield the processed text
        yield processed_text
    
    def _process_compose_content(self, content: str) -> str:
        """Process Docker Compose content into a structured text representation.
        
        This method:
        1. Parses the YAML
        2. Extracts services configuration
        3. Extracts networks, volumes, and other top-level elements
        4. Formats the Docker Compose structure in a readable way
        """
        result = []
        
        try:
            # Parse YAML content
            compose_data = yaml.safe_load(content)
            
            if not compose_data or not isinstance(compose_data, dict):
                return "Invalid Docker Compose file format"
            
            # Extract version
            version = compose_data.get('version')
            if version:
                result.append(f"COMPOSE VERSION: {version}\n")
            
            # Extract services
            services = self._extract_services(compose_data)
            if services:
                result.append("SERVICES:")
                result.extend(services)
                result.append("")
            
            # Extract networks
            networks = self._extract_networks(compose_data)
            if networks:
                result.append("NETWORKS:")
                result.extend(networks)
                result.append("")
            
            # Extract volumes
            volumes = self._extract_volumes(compose_data)
            if volumes:
                result.append("VOLUMES:")
                result.extend(volumes)
                result.append("")
            
            # Extract top-level configs
            configs = self._extract_configs(compose_data)
            if configs:
                result.append("CONFIGS:")
                result.extend(configs)
                result.append("")
            
            # Extract environment variables
            env_vars = self._extract_environment_variables(compose_data)
            if env_vars:
                result.append("ENVIRONMENT VARIABLES:")
                result.extend(env_vars)
                result.append("")
            
            # Extract other top-level elements
            other_elements = self._extract_other_elements(compose_data)
            if other_elements:
                result.append("OTHER CONFIGURATIONS:")
                result.extend(other_elements)
            
        except yaml.YAMLError as e:
            result.append(f"Error parsing Docker Compose file: {str(e)}")
        except Exception as e:
            result.append(f"Unexpected error processing Docker Compose file: {str(e)}")
        
        return "\n".join(result)
    
    def _extract_services(self, compose_data: Dict[str, Any]) -> List[str]:
        """Extract service definitions from Docker Compose data."""
        services = []
        service_data = compose_data.get('services', {})
        
        for service_name, config in service_data.items():
            services.append(f"Service: {service_name}")
            
            # Extract image
            if 'image' in config:
                services.append(f"  Image: {config['image']}")
            
            # Extract build info
            if 'build' in config:
                build_info = config['build']
                if isinstance(build_info, str):
                    services.append(f"  Build: {build_info}")
                elif isinstance(build_info, dict):
                    services.append("  Build:")
                    for key, value in build_info.items():
                        services.append(f"    {key}: {value}")
            
            # Extract ports
            if 'ports' in config:
                services.append("  Ports:")
                ports = config['ports']
                if isinstance(ports, list):
                    for port in ports:
                        services.append(f"    - {port}")
            
            # Extract volumes
            if 'volumes' in config:
                services.append("  Volumes:")
                volumes = config['volumes']
                if isinstance(volumes, list):
                    for volume in volumes:
                        services.append(f"    - {volume}")
            
            # Extract environment
            if 'environment' in config:
                services.append("  Environment:")
                env = config['environment']
                if isinstance(env, list):
                    for item in env:
                        services.append(f"    - {item}")
                elif isinstance(env, dict):
                    for key, value in env.items():
                        services.append(f"    {key}: {value}")
            
            # Extract depends_on
            if 'depends_on' in config:
                services.append("  Depends On:")
                deps = config['depends_on']
                if isinstance(deps, list):
                    for dep in deps:
                        services.append(f"    - {dep}")
                elif isinstance(deps, dict):
                    for dep, condition in deps.items():
                        services.append(f"    {dep}: {condition}")
            
            # Extract networks
            if 'networks' in config:
                services.append("  Networks:")
                networks = config['networks']
                if isinstance(networks, list):
                    for network in networks:
                        services.append(f"    - {network}")
                elif isinstance(networks, dict):
                    for network, net_config in networks.items():
                        if isinstance(net_config, dict):
                            services.append(f"    {network}:")
                            for key, value in net_config.items():
                                services.append(f"      {key}: {value}")
                        else:
                            services.append(f"    {network}: {net_config}")
            
            # Extract restart policy
            if 'restart' in config:
                services.append(f"  Restart Policy: {config['restart']}")
            
            # Add spacing between services
            services.append("")
        
        return services
    
    def _extract_networks(self, compose_data: Dict[str, Any]) -> List[str]:
        """Extract network configurations."""
        networks = []
        networks_data = compose_data.get('networks', {})
        
        for network_name, config in networks_data.items():
            networks.append(f"Network: {network_name}")
            
            if isinstance(config, dict):
                for key, value in config.items():
                    if isinstance(value, dict):
                        networks.append(f"  {key}:")
                        for sub_key, sub_value in value.items():
                            networks.append(f"    {sub_key}: {sub_value}")
                    else:
                        networks.append(f"  {key}: {value}")
            
            networks.append("")
        
        return networks
    
    def _extract_volumes(self, compose_data: Dict[str, Any]) -> List[str]:
        """Extract volume configurations."""
        volumes = []
        volumes_data = compose_data.get('volumes', {})
        
        for volume_name, config in volumes_data.items():
            volumes.append(f"Volume: {volume_name}")
            
            if isinstance(config, dict):
                for key, value in config.items():
                    volumes.append(f"  {key}: {value}")
            
            volumes.append("")
        
        return volumes
    
    def _extract_configs(self, compose_data: Dict[str, Any]) -> List[str]:
        """Extract configs section."""
        configs = []
        configs_data = compose_data.get('configs', {})
        
        for config_name, config in configs_data.items():
            configs.append(f"Config: {config_name}")
            
            if isinstance(config, dict):
                for key, value in config.items():
                    configs.append(f"  {key}: {value}")
            
            configs.append("")
        
        return configs
    
    def _extract_environment_variables(self, compose_data: Dict[str, Any]) -> List[str]:
        """Extract all environment variables from services."""
        env_vars = []
        service_data = compose_data.get('services', {})
        
        for service_name, config in service_data.items():
            if 'environment' in config:
                env_vars.append(f"Service: {service_name}")
                env = config['environment']
                
                if isinstance(env, list):
                    for item in env:
                        # Try to split on '=' for list items
                        if '=' in item:
                            key, value = item.split('=', 1)
                            env_vars.append(f"  {key}: {value}")
                        else:
                            env_vars.append(f"  {item}")
                elif isinstance(env, dict):
                    for key, value in env.items():
                        env_vars.append(f"  {key}: {value}")
                
                env_vars.append("")
        
        return env_vars
    
    def _extract_other_elements(self, compose_data: Dict[str, Any]) -> List[str]:
        """Extract other top-level elements not covered by specific extractors."""
        skip_keys = {'version', 'services', 'networks', 'volumes', 'configs'}
        other = []
        
        for key, value in compose_data.items():
            if key not in skip_keys:
                if isinstance(value, dict):
                    other.append(f"{key}:")
                    for sub_key, sub_value in value.items():
                        other.append(f"  {sub_key}: {sub_value}")
                else:
                    other.append(f"{key}: {value}")
                
                other.append("")
        
        return other