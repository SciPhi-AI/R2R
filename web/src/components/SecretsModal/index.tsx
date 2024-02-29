import { Fragment, useRef, useState, useEffect } from 'react';
import { Dialog, Transition } from '@headlessui/react';

import { Provider } from '@/types';
import styles from './styles.module.scss';

interface SecretsModalProps {
  isOpen: boolean;
  toggleModal: () => void;
  provider: Provider;
}

type EnvVariable = {
  [key: string]: string;
};

const envVariables: EnvVariable[] = [
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
  {
    NAME: 'qdrant',
    QDRANT_HOST: 'fictional_qdrant_host',
    QDRANT_PORT: 'fictional_qdrant_port',
    QDRANT_API_KEY: 'fictional_qdrant_api_key',
  },
];

const SecretsModal: React.FC<SecretsModalProps> = ({
  isOpen,
  toggleModal,
  provider,
}) => {
  // TODO: Use modal instead of passing it as props
  const [secrets, setSecrets] = useState([]);
  const [selectedSecret, setSelectedSecret] = useState('');
  const [secretDetails, setSecretDetails] = useState<EnvVariable>({});

  console.log('Secrets Provider:', provider);

  const cancelButtonRef = useRef(null);

  const cleanProviderName = provider.name.toLowerCase().replace(' ', '_');

  const [tempSecrets, setTempSecrets] = useState<EnvVariable>({});

  useEffect(() => {
    // Temporarily save the secret details whenever they change
    setTempSecrets(secretDetails);
  }, [secretDetails]);

  useEffect(() => {
    // Simulate fetching secrets from backend and update state
    // This is a placeholder for actual fetch call
    const fetchedSecrets = envVariables; // Replace with actual fetch call
    setSecrets(fetchedSecrets);
    if (fetchedSecrets.length > 0) {
      setSelectedSecret(JSON.stringify(fetchedSecrets[0]));
      setSecretDetails(fetchedSecrets[0]);
    }
  }, [provider]);

  const handleSelectChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const { value } = event.target;
    setSelectedSecret(value);

    if (value === '') {
      // Clear the secret details when "Select Secret" is chosen
      setSecretDetails({});
    } else if (value === 'load') {
      // Fetch secrets from backend and update state
      fetch(`/api/get_secrets/${cleanProviderName}`)
        .then((response) => response.json())
        .then((data) => {
          setSecrets(data);
          if (data.length > 0) {
            setSelectedSecret(data[0]);
            setSecretDetails(data[0]);
          }
        })
        .catch((error) => console.error('Error fetching secrets:', error));
    } else if (value === 'new') {
      // Handle new secrets option if needed
      setSecretDetails({
        POSTGRES_USER: '',
        POSTGRES_PASSWORD: '',
        POSTGRES_HOST: '',
        POSTGRES_PORT: '',
        POSTGRES_DBNAME: '',
      });
    } else {
      const selected = secrets.find((secret) => secret === value);
      if (selected) {
        setSecretDetails(selected);
      }
    }
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setSecretDetails((prevDetails) => ({
      ...prevDetails,
      [name]: value,
    }));

    // Assume it's a new secret when user starts typing
    setSelectedSecret('new');
  };

  const saveSecret = () => {
    // Validate form data and send update to backend
    fetch(`/api/update_secrets/${cleanProviderName}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(secretDetails),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log('Secret saved:', data);
        // Show success notification
      })
      .catch((error) => console.error('Error saving secret:', error));
  };

  const deleteSecret = () => {
    // Confirm deletion, send delete request to backend, update UI accordingly
    setSecretDetails({});
    setTempSecrets({});
    fetch(`/api/update_secrets/${cleanProviderName}`, {
      method: 'DELETE',
    })
      .then((response) => response.json())
      .then((data) => {
        console.log('Secret deleted:', data);
        // Show success notification
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
        <div className={styles.dialogBackground} />
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
              <Dialog.Panel className={styles.dialogPanel}>
                <Dialog.Title as="h3" className={styles.title}>
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
                    className={styles.selectInput}
                    value={selectedSecret}
                    onChange={handleSelectChange}
                  >
                    <option value="">Select Secret</option>
                    <option value="load">Load Secret</option>
                    <option value="new">New Secret</option>
                  </select>
                  <form className="mt-4">
                    {Object.entries(secretDetails).map(([key, value]) => (
                      <div key={key} className={styles.flexContainer}>
                        <label className={styles.label}>{key}</label>
                        <p className="text-black">{key}</p>
                        <input
                          type="text"
                          name={key}
                          className={styles.textInput}
                          value={value}
                          onChange={handleInputChange} // Add this line
                        />
                      </div>
                    ))}
                  </form>
                </div>
                <div className="mt-4 flex justify-end">
                  <button
                    type="button"
                    className={styles.deleteButton}
                    onClick={deleteSecret}
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    className={styles.saveButton}
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
