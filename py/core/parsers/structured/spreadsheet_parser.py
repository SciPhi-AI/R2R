"""
Enhanced Spreadsheet Parser for R2R
Processes Excel/CSV files into both structured data and narrative summaries.
"""

import pandas as pd
import json
from typing import Any, Dict, List, Optional, AsyncGenerator
from io import BytesIO

from core.base import AsyncParser
from shared.abstractions import DataType


class SpreadsheetParser(AsyncParser[DataType]):
    """
    Enhanced parser for spreadsheet files that creates both:
    1. Narrative summary for RAG search
    2. Structured data storage for precise queries
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_rows_for_narrative = config.get("max_rows_for_narrative", 100)
        self.generate_narrative = config.get("generate_narrative", True)
        self.store_structured_data = config.get("store_structured_data", True)
    
    async def ingest(
        self, data: DataType, **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process spreadsheet file into narrative and structured data.
        """
        if isinstance(data, bytes):
            file_content = data
        else:
            # Handle file path or other data types
            with open(data, 'rb') as f:
                file_content = f.read()
        
        # Determine file type and parse
        filename = kwargs.get('filename', '')
        
        try:
            # Step 1: Heuristic extraction (standard pandas)
            try:
                if filename.endswith('.xlsx') or filename.endswith('.xls'):
                    df = pd.read_excel(BytesIO(file_content))
                elif filename.endswith('.csv'):
                    df = pd.read_csv(BytesIO(file_content))
                else:
                    raise ValueError(f"Unsupported file type: {filename}")
                
                # Clean and process the dataframe
                df_clean = await self._clean_dataframe(df)
                
            except Exception as heuristic_error:
                # Step 2: LLM fallback for complex layouts
                print(f"Heuristic parsing failed for {filename}, trying LLM fallback: {heuristic_error}")
                df_clean = await self._llm_fallback_parser(file_content, filename)
                
                if df_clean is None:
                    raise ValueError(f"Both heuristic and LLM parsing failed for {filename}")
            
            # Generate narrative summary
            if self.generate_narrative:
                narrative = await self._generate_narrative_summary(df_clean, filename)
                
                yield {
                    "content": narrative,
                    "metadata": {
                        "source_type": "spreadsheet",
                        "filename": filename,
                        "rows": len(df_clean),
                        "columns": len(df_clean.columns),
                        "has_structured_data": self.store_structured_data
                    }
                }
            
            # Store structured data if enabled
            if self.store_structured_data:
                structured_data = await self._prepare_structured_data(df_clean, filename)
                
                # Store in database for SQL queries (if database provider available)
                if hasattr(self, 'database_provider') and self.database_provider:
                    await self._store_in_database(df_clean, filename, kwargs.get('document_id'))
                
                yield {
                    "content": f"Structured data from {filename}",
                    "metadata": {
                        "source_type": "spreadsheet_data",
                        "filename": filename,
                        "structured_data": structured_data,
                        "data_schema": list(df_clean.columns),
                        "has_database_storage": hasattr(self, 'database_provider')
                    }
                }
                
        except Exception as e:
            # Fallback: treat as plain text
            yield {
                "content": f"Error processing spreadsheet {filename}: {str(e)}",
                "metadata": {
                    "source_type": "spreadsheet_error",
                    "filename": filename,
                    "error": str(e)
                }
            }
    
    async def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and normalize the dataframe.
        """
        # Remove completely empty rows and columns
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Handle unnamed columns
        for i, col in enumerate(df.columns):
            if col.startswith('Unnamed:') or col == '':
                df.columns.values[i] = f'Column_{i+1}'
        
        # Convert data types appropriately
        for col in df.columns:
            # Try to convert to numeric if possible
            if df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except:
                    pass
        
        return df
    
    async def _generate_narrative_summary(
        self, df: pd.DataFrame, filename: str
    ) -> str:
        """
        Generate a narrative summary of the spreadsheet data.
        """
        # Basic statistics
        rows, cols = df.shape
        
        # Sample data for narrative (limit rows for performance)
        sample_df = df.head(self.max_rows_for_narrative)
        
        # Generate basic narrative
        narrative_parts = [
            f"# Spreadsheet Analysis: {filename}",
            f"",
            f"This spreadsheet contains {rows} rows and {cols} columns of data.",
            f"",
            f"## Column Structure",
        ]
        
        # Describe each column
        for col in df.columns:
            col_info = self._analyze_column(df[col])
            narrative_parts.append(f"- **{col}**: {col_info}")
        
        # Add data sample
        if len(sample_df) > 0:
            narrative_parts.extend([
                f"",
                f"## Data Sample",
                f"The following shows a sample of the data:",
                f"",
            ])
            
            # Convert sample to readable format
            for idx, row in sample_df.head(5).iterrows():
                row_desc = ", ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
                narrative_parts.append(f"- Row {idx + 1}: {row_desc}")
        
        # Add summary statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            narrative_parts.extend([
                f"",
                f"## Numeric Summary",
            ])
            
            for col in numeric_cols:
                stats = df[col].describe()
                narrative_parts.append(
                    f"- **{col}**: Mean: {stats['mean']:.2f}, "
                    f"Min: {stats['min']:.2f}, Max: {stats['max']:.2f}"
                )
        
        return "\n".join(narrative_parts)
    
    def _analyze_column(self, series: pd.Series) -> str:
        """
        Analyze a column and return a description.
        """
        dtype = series.dtype
        non_null_count = series.count()
        total_count = len(series)
        
        if pd.api.types.is_numeric_dtype(series):
            return f"Numeric data ({dtype}), {non_null_count}/{total_count} non-null values"
        elif pd.api.types.is_datetime64_any_dtype(series):
            return f"Date/time data, {non_null_count}/{total_count} non-null values"
        else:
            unique_count = series.nunique()
            return f"Text data, {non_null_count}/{total_count} non-null values, {unique_count} unique values"
    
    async def _prepare_structured_data(
        self, df: pd.DataFrame, filename: str
    ) -> Dict[str, Any]:
        """
        Prepare structured data for storage and querying.
        """
        # Convert DataFrame to records format
        records = df.to_dict('records')
        
        # Clean records (handle NaN values)
        clean_records = []
        for record in records:
            clean_record = {}
            for key, value in record.items():
                if pd.notna(value):
                    clean_record[key] = value
                else:
                    clean_record[key] = None
            clean_records.append(clean_record)
        
        return {
            "filename": filename,
            "columns": list(df.columns),
            "data_types": {col: str(df[col].dtype) for col in df.columns},
            "row_count": len(df),
            "records": clean_records[:1000],  # Limit for performance
            "schema": {
                col: {
                    "type": str(df[col].dtype),
                    "non_null_count": int(df[col].count()),
                    "unique_count": int(df[col].nunique())
                }
                for col in df.columns
            }
        }
    
    async def _store_in_database(
        self, df: pd.DataFrame, filename: str, document_id: Optional[str]
    ) -> None:
        """
        Store structured data in database for SQL queries (Ellen V2 style).
        """
        try:
            # Create table name from filename
            table_name = f"spreadsheet_{filename.replace('.', '_').replace('-', '_').lower()}"
            
            # Convert DataFrame to records for database storage
            records = []
            for index, row in df.iterrows():
                for col_name, value in row.items():
                    if pd.notna(value):  # Only store non-null values
                        records.append({
                            "document_id": document_id,
                            "filename": filename,
                            "table_name": table_name,
                            "row_index": int(index),
                            "column_name": str(col_name),
                            "cell_value": str(value),
                            "data_type": str(df[col_name].dtype),
                            "created_at": "NOW()"
                        })
            
            # Store in database (would need actual database connection)
            # This is a placeholder - in production you'd use the database provider
            if hasattr(self.database_provider, 'execute_sql'):
                # Create table if not exists
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS spreadsheet_cells (
                    id SERIAL PRIMARY KEY,
                    document_id VARCHAR(255),
                    filename VARCHAR(255),
                    table_name VARCHAR(255),
                    row_index INTEGER,
                    column_name VARCHAR(255),
                    cell_value TEXT,
                    data_type VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """
                await self.database_provider.execute_sql(create_table_sql)
                
                # Insert records in batches
                batch_size = 100
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    # Insert batch (would need proper SQL generation)
                    print(f"Would insert {len(batch)} records for {filename}")
            
        except Exception as e:
            print(f"Database storage error for {filename}: {e}")
    
    async def _llm_fallback_parser(
        self, file_content: bytes, filename: str
    ) -> Optional[pd.DataFrame]:
        """
        LLM fallback for complex spreadsheet layouts (Ellen V2 style).
        """
        if not hasattr(self, 'llm_provider') or not self.llm_provider:
            return None
        
        try:
            # Convert first few rows to text for LLM analysis
            if filename.endswith('.csv'):
                sample_text = file_content[:2000].decode('utf-8', errors='ignore')
            else:
                # For Excel files, would need more sophisticated preview
                sample_text = f"Excel file: {filename} (binary content)"
            
            prompt = f"""
            Analyze this spreadsheet data and generate a parsing specification.
            
            File: {filename}
            Sample content:
            {sample_text}
            
            Generate a JSON specification with:
            1. header_row: Which row contains headers (0-indexed)
            2. data_start_row: Which row data starts (0-indexed)  
            3. columns_to_extract: List of column names/indices to extract
            4. data_cleaning_rules: Any special cleaning needed
            
            Return only valid JSON:
            """
            
            response = await self.llm_provider.aget_completion(
                messages=[{"role": "user", "content": prompt}],
                generation_config={"max_tokens": 300}
            )
            
            # Parse LLM response and apply parsing spec
            spec_text = response.choices[0].message.content
            try:
                import json
                parsing_spec = json.loads(spec_text)
                
                # Apply the parsing specification
                return await self._apply_parsing_spec(file_content, filename, parsing_spec)
                
            except json.JSONDecodeError:
                print(f"LLM returned invalid JSON for {filename}")
                return None
                
        except Exception as e:
            print(f"LLM fallback error for {filename}: {e}")
            return None
    
    async def _apply_parsing_spec(
        self, file_content: bytes, filename: str, spec: Dict[str, Any]
    ) -> Optional[pd.DataFrame]:
        """
        Apply LLM-generated parsing specification to extract data.
        """
        try:
            header_row = spec.get("header_row", 0)
            data_start_row = spec.get("data_start_row", 1)
            
            if filename.endswith('.csv'):
                df = pd.read_csv(
                    BytesIO(file_content),
                    header=header_row,
                    skiprows=range(1, data_start_row) if data_start_row > 1 else None
                )
            else:
                df = pd.read_excel(
                    BytesIO(file_content),
                    header=header_row,
                    skiprows=range(1, data_start_row) if data_start_row > 1 else None
                )
            
            # Apply column filtering if specified
            columns_to_extract = spec.get("columns_to_extract")
            if columns_to_extract:
                available_cols = [col for col in columns_to_extract if col in df.columns]
                if available_cols:
                    df = df[available_cols]
            
            return df
            
        except Exception as e:
            print(f"Error applying parsing spec for {filename}: {e}")
            return None
