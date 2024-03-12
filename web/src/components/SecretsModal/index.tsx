import { Fragment, useRef, useState, useEffect, useCallback } from 'react';
import { Dialog, Transition } from '@headlessui/react';

// rest of your code
import { Provider } from '@/types';

interface SecretsModalProps {
  isOpen: boolean;
  toggleModal: () => void;
  provider: Provider;
}

type EnvironmentVariable = {
  [key: string]: string;
};

type SecretsProvider = 'Postgres' | 'Qdrant' | 'other';

const serviceEnvironmentVariables: Record<
  SecretsProvider,
  EnvironmentVariable[]
> = {
  Postgres: [
    {
      NAME: 'supabase-dev',
      POSTGRES_USER: 'postgres.fictionaluser',
      POSTGRES_PASSWORD: 'secretfictionalpass',
      POSTGRES_HOST: 'cloud-0-fake-region-1.database.fictionalcloud.com',
      POSTGRES_PORT: '5432',
      POSTGRES_DBNAME: 'postgres_fictional_db',
    },
    {
      NAME: 'supabase-prod',
      POSTGRES_USER: 'postgres.acme',
      POSTGRES_PASSWORD: 'secretfictionalpass',
      POSTGRES_HOST: 'cloud-0-fake-region-1.database.fictionalcloud.com',
      POSTGRES_PORT: '5400',
      POSTGRES_DBNAME: 'postgres_fictional_large_db',
    },
  ],
  Qdrant: [
    {
      NAME: 'qdrant-dev',
      QDRANT_HOST: 'fictional_qdrant_host',
      QDRANT_PORT: 'fictional_qdrant_port',
      QDRANT_API_KEY: 'fictional_qdrant_api_key',
    },
  ],
  other: [
    {
      NAME: 'other',
      OTHER_ENV_VAR_1: 'default_value_1',
      OTHER_ENV_VAR_2: 'default_value_2',
    },
  ],
};

const SecretsModal: React.FC<SecretsModalProps> = ({
  isOpen,
  toggleModal,
  provider,
}) => {
  // TODO: Use modal instead of passing it as props
  const [secrets, setSecrets] = useState([]);
  const [selectedSecret, setSelectedSecret] = useState<string | null>(null);
  const [secretDetails, setSecretDetails] = useState<EnvironmentVariable>({});
  const cancelButtonRef = useRef(null);

  const NEW_SECRET = 'new';
  const LOAD_SECRET = 'load';
  const PROVIDERS = ['Postgres', 'Qdrant'];

  const [tempSecrets, setTempSecrets] = useState<EnvironmentVariable>({});

  const cleanString = (input: string): string => {
    if (input === undefined) {
      return '';
    }
    return input.toLowerCase().replace(' ', '_');
  };

  const cleanProviderSource = cleanString(provider.name);
  const cleanSecretName = cleanString(secretDetails.name);

  useEffect(() => {
    // Temporarily save the secret details whenever they change
    setTempSecrets(secretDetails);
  }, [secretDetails]);

  useEffect(() => {
    // Simulate fetching secrets from backend and update state
    const providerName = PROVIDERS.includes(provider.name)
      ? provider.name
      : 'other';
    const fetchedSecrets =
      serviceEnvironmentVariables[providerName as SecretsProvider]; // Replace with actual fetch call
    if (fetchedSecrets) {
      setSecrets(fetchedSecrets);

      // Create a new secret template with the same keys as the first fetched secret
      const newSecretTemplate = Object.fromEntries(
        Object.keys(fetchedSecrets[0]).map((key) => [key, ''])
      );
      setSecretDetails(newSecretTemplate);
    }
  }, [provider]);

  const fetchSecrets = useCallback(
    async ({
      providerSource,
      secretName,
    }: {
      providerSource: string;
      secretName: string;
    }) => {
      try {
        const response = await fetch(
          `/api/secrets?provider=${cleanProviderSource}&secretName=${cleanSecretName}`
        );
        const data = await response.json();
        setSecrets(data.secrets);
      } catch (error) {
        console.error('Error fetching secrets:', error);
      }
    },
    []
  );

  const handleSelectChange = useCallback(
    async (event: React.ChangeEvent<HTMLSelectElement>) => {
      const { value } = event.target;
      setSelectedSecret(value);

      if (value === '') {
        setSecretDetails({});
      } else if (value === LOAD_SECRET) {
        await fetchSecrets({
          providerSource: provider.name,
          secretName: secretDetails.name,
        });
      } else if (value === NEW_SECRET) {
        const defaultName = `${provider.name.toLowerCase()}-${secrets.length + 1}`;
        const emptySecret = Object.fromEntries(
          Object.keys(secretDetails).map((key) => [key, ''])
        );
        setSecretDetails({
          ...emptySecret,
          NAME: defaultName,
        });
      } else {
        const selected = secrets.find((secret) => secret.NAME === value);
        if (selected) {
          setSecretDetails(selected);
        }
      }
    },
    [fetchSecrets, provider.name, secrets.length, secretDetails]
  );

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setSecretDetails((prevDetails) => ({
      ...prevDetails,
      [name]: value,
    }));

    // Assume it's a new secret when user starts typing
    setSelectedSecret(NEW_SECRET);
  };

  const saveSecret = () => {
    // Validate form data and send update to backend
    fetch(
      `/api/secrets?provider=${cleanProviderSource}&secretName=${cleanSecretName}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(secretDetails),
      }
    )
      .then((response) => response.json())
      .then((data) => {
        // console.log('Secret saved:', data);
        // Show success notification
      })
      .catch((error) => console.error('Error saving secret:', error));
  };

  const deleteSecret = () => {
    // Confirm deletion, send delete request to backend, update UI accordingly
    fetch(
      `/api/secrets?provider=${cleanProviderSource}&secretName=${cleanSecretName}`,
      {
        method: 'DELETE',
      }
    )
      .then((response) => response.json())
      .then((data) => {
        // Show success notification
        // console.log('Secret deleted:', data);
        // Remove the deleted secret from the secrets array
        const updatedSecrets = secrets.filter(
          (secret) => secret.NAME !== selectedSecret
        );
        setSecrets(updatedSecrets);

        // Select a new secret or 'new' if no other secrets exist
        let newSelectedSecret;
        if (updatedSecrets.length > 0) {
          newSelectedSecret = updatedSecrets[0].NAME;
        } else {
          newSelectedSecret = NEW_SECRET;
        }
        setSelectedSecret(newSelectedSecret);

        // Update secretDetails with the details of the new selected secret or a new secret template
        const newSecretDetails =
          updatedSecrets.find((secret) => secret.NAME === newSelectedSecret) ||
          Object.fromEntries(
            Object.keys(secretDetails).map((key) => [key, ''])
          );
        setSecretDetails(newSecretDetails);

        // Clear the temp secrets
        setTempSecrets({});
      })
      .catch((error) => console.error('Error deleting secret:', error));
  };

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-10"
        initialFocus={cancelButtonRef}
        onClose={toggleModal}
      >
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg bg-white p-6 text-left align-middle shadow-xl transition-all">
                <Dialog.Title
                  as="h3"
                  className="text-lg font-medium leading-6 text-gray-900"
                >
                  {' '}
                  <div className="flex items-center">
                    <img
                      src={`/images/${provider.logo}`}
                      alt={`${provider.name} Logo`}
                      style={{
                        width: '20px',
                        height: '20px',
                        marginRight: '8px',
                      }}
                    />
                    {provider.name} Secrets Manager
                  </div>
                </Dialog.Title>
                <div className="mt-2">
                  <select
                    className="block w-full rounded-md border-gray-300 shadow-sm text-black bg-gray-200 px-3 py-2"
                    value={selectedSecret}
                    onChange={handleSelectChange}
                  >
                    <option value="" disabled={selectedSecret !== null}>
                      Select Secret
                    </option>
                    {secrets.map((secret) => (
                      <option key={secret.NAME} value={secret.NAME}>
                        {secret.NAME}
                      </option>
                    ))}
                    <option value="new">New Secret</option>
                  </select>
                  <form className="mt-4">
                    {Object.entries(secretDetails).map(([key, value]) => (
                      <div key={key} className="flex items-center mb-4">
                        <label className="block text-sm font-medium text-gray-700 mr-4">
                          {key}
                        </label>
                        <input
                          type="text"
                          name={key}
                          className="block w-full rounded-md border-gray-300 shadow-sm text-black bg-gray-200 px-3 py-2"
                          value={value}
                          onChange={handleInputChange}
                        />
                      </div>
                    ))}
                  </form>
                </div>
                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    className="inline-flex justify-center rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
                    onClick={deleteSecret}
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    className="ml-4 inline-flex justify-center rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
                    onClick={saveSecret}
                  >
                    Save
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default SecretsModal;
