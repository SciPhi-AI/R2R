import Layout from '@/components/Layout';
import {
  CardTitle,
  CardDescription,
  CardHeader,
  CardContent,
  CardFooter,
  Card,
} from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import styles from '../../styles/Index.module.scss';
import { useState } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Info } from 'lucide-react';
import { useRouter } from 'next/router';
import { createClient } from '@/utils/supabase/component';
// import CryptoJS from 'crypto-js';

function Component() {
  const [secretPairs, setSecretPairs] = useState([{ key: '', value: '' }]);
  const [selectedApiKey, setSelectedApiKey] = useState('');
  const [availableApiKeys, setAvailableApiKeys] = useState([
    { value: 'key1', label: 'API Key 1' },
    { value: 'key2', label: 'API Key 2' },
    // Add more available API keys as needed
  ]);
  const [newPublicKey, setNewPublicKey] = useState('');
  const [newPrivateKey, setNewPrivateKey] = useState('');
  const [newApiKeyName, setNewApiKeyName] = useState('');
  const [pipelineName, setPipelineName] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const handleAddMore = () => {
    setSecretPairs([...secretPairs, { key: '', value: '' }]);
  };
  const router = useRouter();
  const supabase = createClient();

  const handleRemove = (index) => {
    const updatedPairs = [...secretPairs];
    updatedPairs.splice(index, 1);
    setSecretPairs(updatedPairs);
  };

  const handleSecretKeyChange = (index, value) => {
    const updatedPairs = [...secretPairs];
    updatedPairs[index].key = value;
    setSecretPairs(updatedPairs);
  };

  const handleSecretValueChange = (index, value) => {
    const updatedPairs = [...secretPairs];
    updatedPairs[index].value = value;
    setSecretPairs(updatedPairs);
  };

  const handleGenerateApiKey = () => {
    console.log('generating new api key...');
    // Generate a new public key and private key
    const newPublicKey = generatePublicKey();
    const newPrivateKey = generatePrivateKey();

    // Generate a default name for the API key
    const defaultName = `API Key ${availableApiKeys.length + 1}`;

    // Add the new API key to the available keys
    const newApiKey = { value: newPublicKey, label: defaultName };
    // setAvailableApiKeys([...availableApiKeys, newApiKey]);

    // Set the new public key, private key, and API key name in the state
    setNewPublicKey(newPublicKey);
    setNewPrivateKey(newPrivateKey);
    setNewApiKeyName(defaultName);

    // Select the newly generated API key
    setSelectedApiKey('generate');
  };

  const generatePublicKey = () => {
    // Generate a new public key (replace with your own logic)
    return `pk-${Math.random().toString(36)}`;
  };

  const generatePrivateKey = () => {
    // Generate a new private key (replace with your own logic)
    return `sk-${Math.random().toString(36)}`;
  };
  const handleApiKeyChange = (value) => {
    if (value === 'generate') {
      handleGenerateApiKey();
    } else if (value === 'No API Key') {
      setNewPublicKey('');
      setNewPrivateKey('');
      setSelectedApiKey(value);
    } else {
      setSelectedApiKey(value);
    }
  };
  const handleSubmit = async () => {
    const formData = {
      pipeline_name: pipelineName,
      repo_url: githubUrl,
      // selectedApiKey,
      // secretPairs: encryptedSecretPairs,
    };

    try {
      // Get the current session token
      const session = await supabase.auth.getSession();
      const token = session.data?.session?.access_token;

      if (!token) {
        // Handle case when token is not available
        console.error('Access token not found');
        // Display an error message to the user or redirect to login page
        return;
      }

      // Make a POST request to the create_pipeline API
      const response = await fetch('/api/create_pipeline', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        // Pipeline creation successful
        console.log('Pipeline created successfully');
        // Reset the form fields
        setPipelineName('');
        setGithubUrl('');
        setSelectedApiKey('');
        setSecretPairs([{ key: '', value: '' }]);
        setNewPublicKey('');
        setNewPrivateKey('');
        // Redirect to a success page or display a success message
        router.push('/');
      } else {
        // Pipeline creation failed
        console.error('Pipeline creation failed');
        // Display an error message to the user
        alert('Failed to create the pipeline. Please try again.');
      }
    } catch (error) {
      console.error('Error creating pipeline:', error);
      // Display an error message to the user
      alert('An error occurred while creating the pipeline. Please try again.');
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Deploy a RAG pipeline</CardTitle>
        <CardDescription>
          To deploy a new Pipeline, import an existing GitHub Repository or
          select a template.
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <CardContent className="space-y-4 w-full">
          <div className="grid grid-cols-12 gap-8">
            <div className="col-span-8 left-content">
              <div className="mb-8">
                <div className="space-y-2">
                  <Label htmlFor="project-name">Pipeline Name</Label>
                  <Input
                    placeholder="Name Your Pipeline"
                    className="w-full"
                    onChange={(e) => setPipelineName(e.target.value)}
                    value={pipelineName}
                  />
                </div>
                <div className="space-y-2 mt-1">
                  <Label htmlFor="github-url">GitHub URL</Label>
                  <Input
                    key="github-url"
                    id="github-url"
                    placeholder="Enter your GitHub URL"
                    className="w-full"
                    onChange={(e) => setGithubUrl(e.target.value)}
                    value={githubUrl}
                  />
                </div>
              </div>

              {secretPairs.map((pair, index) => (
                <div
                  key={index}
                  className="grid grid-cols-12 gap-4 items-center"
                >
                  <div className="col-span-5 space-y-2">
                    {index === 0 && (
                      <Label htmlFor={`secret-key-${index + 1}`}>
                        Secret Key(s)
                      </Label>
                    )}
                    <Input
                      id={`secret-key-${index + 1}`}
                      placeholder="e.g. `OPENAI_API_KEY`"
                      value={pair.key}
                      onChange={(e) =>
                        handleSecretKeyChange(index, e.target.value)
                      }
                    />
                  </div>
                  <div className="col-span-6 space-y-2">
                    {index === 0 && (
                      <Label htmlFor={`secret-value-${index + 1}`}>
                        Secret Value(s)
                      </Label>
                    )}
                    <Input
                      id={`secret-value-${index + 1}`}
                      placeholder="e.g. `sk-bDaW...`"
                      value={pair.value}
                      onChange={(e) =>
                        handleSecretValueChange(index, e.target.value)
                      }
                    />
                  </div>
                  <div className="col-span-1 flex justify-end">
                    <button
                      className={
                        'bg-red-500 hover:bg-red-700 text-white font-bold py-1 px-2 rounded text-xs ' +
                        (index === 0 ? 'mt-7' : '')
                      }
                      onClick={() => handleRemove(index)}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
              <div className="flex justify-end mt-2">
                <button
                  className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded text-xs"
                  onClick={handleAddMore}
                >
                  {secretPairs.length === 0 ? 'Add secret' : 'Add more secrets'}
                </button>
              </div>
              <div className="space-y-2">
                <Label htmlFor="api-key">Select API Key</Label>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <Info className="h-4 w-4 pt-1 text-gray-500" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>
                        Selecting an API key will protect your application
                        during deployment.
                        <br />
                        API keys enable secure communication between your
                        application and the server.
                        <br />
                        <br />
                        Select `No API Key` to allow unauthenticated access to
                        your application.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <Select
                  value={selectedApiKey}
                  onValueChange={handleApiKeyChange}
                >
                  <SelectTrigger>
                    {/* className="w-[300px]"> */}
                    <SelectValue placeholder="Select an API Key" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectLabel>Available API Keys</SelectLabel>
                      {availableApiKeys.map((apiKey) => (
                        <SelectItem key={apiKey.value} value={apiKey.value}>
                          {apiKey.label}
                        </SelectItem>
                      ))}
                      <SelectItem key="No API Key" value={'No API Key'}>
                        No API Key
                      </SelectItem>
                      <SelectItem value="generate">
                        Generate New API Key
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                {newPublicKey && (
                  <div className="mt-2">
                    <Label htmlFor="api-key-name">
                      API Key Name (optional)
                    </Label>
                    <Input
                      id="api-key-name"
                      placeholder={newApiKeyName}
                      value={newApiKeyName}
                      onChange={(e) => setNewApiKeyName(e.target.value)}
                    />
                  </div>
                )}
                {newPublicKey && (
                  <div className="mt-2">
                    <Label>New Public Key:</Label>
                    <Input value={newPublicKey} readOnly />
                  </div>
                )}
                {newPrivateKey && (
                  <div className="mt-2">
                    <Label>New Private Key:</Label>
                    <Input value={newPrivateKey} readOnly />
                    <p className="text-red-500 mt-1">
                      Warning: Your private key will not be saved. Please store
                      it securely.
                    </p>
                  </div>
                )}
              </div>
              <div className="flex justify-end mt-4">
                <button
                  className="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded w-1/3"
                  onClick={handleSubmit}
                >
                  Deploy
                </button>
              </div>
            </div>
            <div className="col-span-4 right-content ">
              <div className="space-y-2 ">R2R Templates</div>
              <Card
                className="w-100px mt-2 cursor-pointer hover:shadow-lg transition-shadow duration-300"
                onClick={() => {
                  // Your onClick logic here
                  console.log('Card clicked!');
                  setPipelineName('Basic RAG');
                  setGithubUrl(
                    'https://github.com/SciPhi-AI/R2R-basic-rag-template'
                  );
                }}
              >
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>Basic RAG</CardTitle>
                  <CardDescription>
                    Ingest documents and answer questions
                  </CardDescription>
                </CardHeader>
              </Card>
              <Card
                className="w-100px mt-2 cursor-pointer hover:shadow-lg transition-shadow duration-300"
                onClick={() => {
                  // Your onClick logic here
                  console.log('Card clicked!');
                  setPipelineName('Synthetic Queries');
                  setGithubUrl(
                    'https://github.com/SciPhi-AI/R2R-synthetic-queries-template'
                  );
                }}
              >
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>Synthetic Queries</CardTitle>
                  <CardDescription>
                    RAG w/ LLM generated synthetic queries
                  </CardDescription>
                </CardHeader>
              </Card>
            </div>
          </div>
        </CardContent>
      </CardFooter>
    </Card>
  );
}

export default function Deploy() {
  return (
    <Layout>
      <main className={styles.main}>
        <div>
          <Component />
        </div>
      </main>
    </Layout>
  );
}
