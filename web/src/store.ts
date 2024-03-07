import { readFile, writeFile } from 'fs/promises';
import { Pipeline } from '@/types';

class Store {
  private filename: string;
  private data: Record<string, Pipeline>; 

  constructor(filename: string) {
    this.filename = filename;
    this.data = {};
  }

  async loadData(): Promise<void> {
    try {
      const fileContents = await readFile(this.filename, 'utf-8');
      this.data = JSON.parse(fileContents);
    } catch (error) {
      console.error('Failed to load data:', error);
      // Initialize file with empty object if it doesn't exist
      this.data = {};
      await this.saveData();
    }
  }

  async saveData(): Promise<void> {
    try {
      const fileContents = JSON.stringify(this.data, null, 2);
      await writeFile(this.filename, fileContents, 'utf-8');
    } catch (error) {
      console.error('Failed to save data:', error);
    }
  }

  getPipeline(id: string): Pipeline | undefined {
    return this.data[id];
  }

  getAllPipelines(): Pipeline[] {
    return Object.values(this.data);
  }

  updatePipeline(id: string, pipeline: Pipeline): void {
    this.data[id] = pipeline;
    this.saveData().catch(console.error);
  }
}

export const store = new Store('./temp_pipelines_store.json');