# type: ignore
from typing import AsyncGenerator, List
import re

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class DockerfileParser(AsyncParser[str | bytes]):
    """A parser for Dockerfile files."""

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
        """Ingest Dockerfile content and yield structured text representation.
        
        Extracts instructions, base images, environment variables, ports, and other
        configuration elements from Dockerfiles in a text format suitable for analysis.
        
        :param data: The Dockerfile content to parse
        :param kwargs: Additional keyword arguments
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")
        
        # Process the Dockerfile content
        processed_text = self._process_dockerfile_content(data)
        
        # Yield the processed text
        yield processed_text
    
    def _process_dockerfile_content(self, content: str) -> str:
        """Process Dockerfile content into a structured text representation.
        
        This method:
        1. Parses the Dockerfile instructions
        2. Extracts base image, stages, environment variables, etc.
        3. Formats the Dockerfile structure in a readable way
        """
        # Preprocess to handle line continuations
        content = self._preprocess_content(content)
        
        # Extract comments
        comments = self._extract_comments(content)
        
        # Parse instructions
        instructions = self._parse_instructions(content)
        
        # Extract specific information
        base_images = self._extract_base_images(instructions)
        stages = self._extract_stages(instructions)
        env_vars = self._extract_env_vars(instructions)
        exposed_ports = self._extract_exposed_ports(instructions)
        volumes = self._extract_volumes(instructions)
        commands = self._extract_commands(instructions)
        
        # Build the result
        result = []
        
        if base_images:
            result.append("BASE IMAGES:")
            result.extend(base_images)
            result.append("")
        
        if stages:
            result.append("BUILD STAGES:")
            result.extend(stages)
            result.append("")
        
        if comments:
            result.append("COMMENTS:")
            result.extend(comments)
            result.append("")
        
        if env_vars:
            result.append("ENVIRONMENT VARIABLES:")
            result.extend(env_vars)
            result.append("")
        
        if exposed_ports:
            result.append("EXPOSED PORTS:")
            result.extend(exposed_ports)
            result.append("")
        
        if volumes:
            result.append("VOLUMES:")
            result.extend(volumes)
            result.append("")
        
        if commands:
            result.append("RUN, CMD, AND ENTRYPOINT:")
            result.extend(commands)
            result.append("")
        
        result.append("DOCKERFILE STRUCTURE:")
        result.extend([f"{i}. {instr}" for i, instr in enumerate(instructions, 1)])
        
        return "\n".join(result)
    
    def _preprocess_content(self, content: str) -> str:
        """Preprocess Dockerfile content to handle line continuations."""
        # Replace line continuations
        content = re.sub(r'\\\n', ' ', content)
        return content
    
    def _extract_comments(self, content: str) -> List[str]:
        """Extract comments from Dockerfile content."""
        comments = []
        comment_pattern = r'^\s*#\s*(.*?)$'
        
        for line in content.split('\n'):
            comment_match = re.match(comment_pattern, line)
            if comment_match:
                comment = comment_match.group(1).strip()
                if comment:
                    comments.append(comment)
        
        return comments
    
    def _parse_instructions(self, content: str) -> List[str]:
        """Parse Dockerfile instructions into a list."""
        instructions = []
        current_instruction = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Check if this is a new instruction
            instruction_match = re.match(r'^(\w+)\s+(.*?)$', line)
            if instruction_match:
                if current_instruction:
                    instructions.append(current_instruction)
                
                instruction = instruction_match.group(1).upper()
                args = instruction_match.group(2)
                current_instruction = f"{instruction} {args}"
            elif current_instruction:
                # Continuation of previous instruction
                current_instruction += f" {line}"
        
        # Add the last instruction
        if current_instruction:
            instructions.append(current_instruction)
        
        return instructions
    
    def _extract_base_images(self, instructions: List[str]) -> List[str]:
        """Extract base images from FROM instructions."""
        base_images = []
        
        for instr in instructions:
            if instr.startswith('FROM '):
                # Handle multi-stage builds
                match = re.match(r'FROM\s+([^\s]+)(?:\s+AS\s+([^\s]+))?', instr)
                if match:
                    image = match.group(1)
                    stage = match.group(2)
                    if stage:
                        base_images.append(f"{image} (Stage: {stage})")
                    else:
                        base_images.append(image)
        
        return base_images
    
    def _extract_stages(self, instructions: List[str]) -> List[str]:
        """Extract build stages from FROM instructions."""
        stages = []
        
        for instr in instructions:
            if instr.startswith('FROM '):
                match = re.search(r'AS\s+([^\s]+)', instr)
                if match:
                    stage_name = match.group(1)
                    stages.append(stage_name)
        
        return stages
    
    def _extract_env_vars(self, instructions: List[str]) -> List[str]:
        """Extract environment variables from ENV instructions."""
        env_vars = []
        
        for instr in instructions:
            if instr.startswith('ENV '):
                env_part = instr[4:].strip()
                
                # Handle multiple env vars in a single instruction
                # ENV key=value key2=value2
                env_parts = []
                parts = re.findall(r'(\w+)=([^\s]+|\".+?\"|\'.+?\')', env_part)
                for key, value in parts:
                    env_parts.append(f"{key}={value}")
                
                # If no explicit equals sign, try space separation: ENV key value
                if not parts:
                    parts = env_part.split(' ', 1)
                    if len(parts) == 2:
                        env_parts.append(f"{parts[0]}={parts[1]}")
                
                env_vars.extend(env_parts)
        
        # Also check ARG instructions
        for instr in instructions:
            if instr.startswith('ARG '):
                arg_part = instr[4:].strip()
                parts = arg_part.split('=', 1)
                key = parts[0]
                value = parts[1] if len(parts) > 1 else "<build-time variable>"
                env_vars.append(f"{key}={value} (Build ARG)")
        
        return env_vars
    
    def _extract_exposed_ports(self, instructions: List[str]) -> List[str]:
        """Extract exposed ports from EXPOSE instructions."""
        ports = []
        
        for instr in instructions:
            if instr.startswith('EXPOSE '):
                port_part = instr[7:].strip()
                # Split by spaces to get multiple ports in a single EXPOSE
                for port in port_part.split():
                    ports.append(port)
        
        return ports
    
    def _extract_volumes(self, instructions: List[str]) -> List[str]:
        """Extract volumes from VOLUME instructions."""
        volumes = []
        
        for instr in instructions:
            if instr.startswith('VOLUME '):
                volume_part = instr[7:].strip()
                
                # Handle JSON array format: VOLUME ["vol1", "vol2"]
                if volume_part.startswith('['):
                    json_vols = re.findall(r'\"([^\"]+)\"|\'([^\']+)\'', volume_part)
                    for vol_groups in json_vols:
                        for vol in vol_groups:
                            if vol:
                                volumes.append(vol)
                else:
                    # Handle space-separated format: VOLUME /vol1 /vol2
                    for vol in volume_part.split():
                        volumes.append(vol)
        
        return volumes
    
    def _extract_commands(self, instructions: List[str]) -> List[str]:
        """Extract RUN, CMD, and ENTRYPOINT instructions."""
        commands = []
        
        for instr in instructions:
            if instr.startswith(('RUN ', 'CMD ', 'ENTRYPOINT ')):
                commands.append(instr)
        
        return commands