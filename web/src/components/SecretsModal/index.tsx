import { Fragment, useRef, useState, useEffect } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { useModal } from '../../hooks/useModal';
import { Provider } from '@/types';

interface SecretsModalProps {
  isOpen: boolean;
  toggleModal: () => void;
  provider: Provider;
}

const SecretsModal: React.FC<SecretsModalProps> = ({
  isOpen,
  toggleModal,
  provider,
}) => {
  const [secrets, setSecrets] = useState([]);
  const [selectedSecret, setSelectedSecret] = useState('');
  const [secretDetails, setSecretDetails] = useState({
    name: '',
    detail1: '',
    detail2: '',
    detail3: '',
    detail4: '',
  });

  const cancelButtonRef = useRef(null);

  useEffect(() => {
    // Fetch secrets from backend and update state
    fetch('YOUR_BACKEND_ENDPOINT')
      .then((response) => response.json())
      .then((data) => setSecrets(data))
      .catch((error) => console.error('Error fetching secrets:', error));
  }, []);

  const handleSelectChange = (event) => {
    const selected = secrets.find((secret) => secret.id === event.target.value);
    setSelectedSecret(selected.id);
    setSecretDetails({ ...selected });
  };

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setSecretDetails((prevDetails) => ({
      ...prevDetails,
      [name]: value,
    }));
  };

  const saveSecret = () => {
    // Validate form data and send update to backend
    // Show success notification
    console.log('Secret saved');
  };

  const deleteSecret = () => {
    // Confirm deletion, send delete request to backend, update UI accordingly
    // Show success notification
    console.log('Secret deleted');
  };

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-10"
        initialFocus={cancelButtonRef}
        onClose={() => {
          toggleModal();
        }}
      >
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        <div className="fixed inset-0 z-10 overflow-y-auto">
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
                  <div className="flex items-center">
                    {' '}
                    <img
                      src={`/images/${provider.logo}`}
                      alt="Logo"
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
                    className="textmt-2 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                    value={selectedSecret}
                    onChange={handleSelectChange}
                  >
                    <option value="">Select a secret</option>
                    {secrets.map((secret) => (
                      <option key={secret.id} value={secret.id}>
                        {secret.name}
                      </option>
                    ))}
                  </select>
                  <form className="mt-4">
                    <input
                      type="text"
                      name="name"
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      value={secretDetails.name}
                      onChange={handleInputChange}
                    />
                    {/* Repeat for other details with similar input fields */}
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
