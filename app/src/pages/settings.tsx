import { SquarePen } from 'lucide-react';
import React, { useState, useEffect, useCallback } from 'react';

import EditPromptDialog from '@/components/ChatDemo/utils/editPromptDialog';
import Layout from '@/components/Layout';
import { useUserContext } from '@/context/UserContext';

type Prompt = {
  name: string;
  template: string;
  input_types: Record<string, any>;
};

interface AppData {
  config: Record<string, any>;
  prompts: Record<string, Prompt>;
}

const renderNestedConfig = (
  config: Record<string, any>,
  depth = 0
): JSX.Element => {
  if (typeof config !== 'object' || config === null) {
    return (
      <span className="whitespace-pre-wrap">
        {JSON.stringify(config, null, 2)}
      </span>
    );
  }

  const isBottomLevel = Object.values(config).every(
    (value) => typeof value !== 'object' || value === null
  );

  return (
    <>
      {Object.entries(config).map(([key, value], index) => (
        <tr
          key={key}
          className={
            (depth <= 1 || isBottomLevel) && index !== 0
              ? 'border-t border-gray-600'
              : ''
          }
        >
          <td
            className={`w-1/3 px-4 py-2 text-white text-center ${depth === 0 ? 'font-bold' : ''}`}
            style={{ paddingLeft: `${depth * 20}px` }}
          >
            {key}
          </td>
          <td className="w-2/3 px-4 py-2 text-white text-left">
            {typeof value === 'object' && value !== null ? (
              renderNestedConfig(value, depth + 1)
            ) : (
              <span className="whitespace-pre-wrap">
                {JSON.stringify(value, null, 2)}
              </span>
            )}
          </td>
        </tr>
      ))}
    </>
  );
};

const Index: React.FC = () => {
  const [appData, setAppData] = useState<AppData | null>(null);
  const [activeTab, setActiveTab] = useState('config');
  const [selectedPromptName, setSelectedPromptName] = useState<string>('');
  const [selectedPromptTemplate, setSelectedPromptTemplate] =
    useState<string>('');
  const [isEditPromptDialogOpen, setIsEditPromptDialogOpen] = useState(false);
  const { pipeline, getClient } = useUserContext();

  const fetchAppData = useCallback(async () => {
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      const response = await client.appSettings();
      if (response && response.results) {
        const { config, prompts } = response.results;
        setAppData({
          config: typeof config === 'string' ? JSON.parse(config) : config,
          prompts: prompts || {},
        });
      } else {
        throw new Error('Unexpected response structure');
      }
    } catch (err) {
      console.error('Error fetching app data:', err);
    }
  }, [getClient]);

  useEffect(() => {
    if (pipeline?.deploymentUrl) {
      fetchAppData();
    }
  }, [pipeline?.deploymentUrl, fetchAppData]);

  const { config = {}, prompts = {} } = appData || {};

  const handleEditPrompt = (name: string, template: string) => {
    setSelectedPromptName(name);
    setSelectedPromptTemplate(template);
    setIsEditPromptDialogOpen(true);
  };

  const handleSaveSuccess = () => {
    if (pipeline?.deploymentUrl) {
      fetchAppData();
    }
  };

  return (
    <Layout pageTitle="Settings">
      <main className="w-full flex flex-col min-h-screen container bg-zinc-900 text-white p-4 mt-4">
        <div className="mx-auto w-full max-w-5xl mb-12 mt-4">
          <div className="mt-8">
            <div className="flex justify-between items-center mb-4">
              <div className="flex justify-center ml-auto">
                <button
                  className={`px-4 py-2 rounded mr-2 ${
                    activeTab === 'config'
                      ? 'bg-blue-500 text-white'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}
                  onClick={() => setActiveTab('config')}
                >
                  Config
                </button>
                <button
                  className={`px-4 py-2 rounded ${
                    activeTab === 'prompts'
                      ? 'bg-blue-500 text-white'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}
                  onClick={() => setActiveTab('prompts')}
                >
                  Prompts
                </button>
              </div>
            </div>
            <div className="bg-zinc-800 p-4 rounded">
              {activeTab === 'config' && (
                <>
                  <h4 className="text-xl font-bold text-white pb-2">Config</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full bg-zinc-800 border border-gray-600">
                      <thead>
                        <tr className="border-b border-gray-600">
                          <th className="w-1/3 px-4 py-2 text-left text-white">
                            Key
                          </th>
                          <th className="w-2/3 px-4 py-2 text-left text-white">
                            Value
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {config && Object.keys(config).length > 0 ? (
                          renderNestedConfig(config)
                        ) : (
                          <tr>
                            <td
                              colSpan={2}
                              className="px-4 py-2 text-white text-center"
                            >
                              No valid configuration data available
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {activeTab === 'prompts' && (
                <>
                  <h4 className="text-xl font-bold text-white pb-2">Prompts</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full bg-zinc-800 border border-gray-600">
                      <thead>
                        <tr className="border-b border-gray-600">
                          <th className="w-1/3 px-4 py-2 text-left text-white">
                            Name
                          </th>
                          <th className="w-2/3 px-4 py-2 text-left text-white">
                            Template
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(prompts).length > 0 ? (
                          Object.entries(prompts).map(([name, prompt]) => (
                            <tr key={name} className="border-t border-gray-600">
                              <td className="w-1/3 px-4 py-2 text-white">
                                {name}
                              </td>
                              <td className="w-2/3 px-4 py-2 text-white relative">
                                <div className="whitespace-pre-wrap font-sans pr-8 max-h-32 overflow-y-auto">
                                  {prompt.template}
                                </div>
                                <button
                                  onClick={() =>
                                    handleEditPrompt(name, prompt.template)
                                  }
                                  className="absolute top-2 right-2 text-gray-400 cursor-pointer hover:text-blue-500"
                                >
                                  <SquarePen className="h-5 w-5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td
                              colSpan={2}
                              className="px-4 py-2 text-white text-center"
                            >
                              No prompts available
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </main>
      <EditPromptDialog
        open={isEditPromptDialogOpen}
        onClose={() => setIsEditPromptDialogOpen(false)}
        promptName={selectedPromptName}
        promptTemplate={selectedPromptTemplate}
        onSaveSuccess={handleSaveSuccess}
      />
    </Layout>
  );
};

export default Index;
