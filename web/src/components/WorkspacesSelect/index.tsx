import { Fragment, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Menu, Transition } from '@headlessui/react';
import { ChevronDownIcon } from '@heroicons/react/20/solid';

import { createClient } from '@/utils/supabase/component';
import { useAuth } from '@/context/authProvider';
import { Pipeline } from '@/types';

import styles from './styles.module.scss';

function WorkspacesSelect() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const pipelinesRef = useRef(pipelines);
  const router = useRouter();
  const { cloudMode } = useAuth();
  const { pipelineName } = router.query;
  const pipeline = pipelines.find((p) => p.id?.toString() === pipelineName);
  const supabase = createClient();

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);

  useEffect(() => {
    fetchPipelines();
    const interval = setInterval(() => {
      if (
        pipelinesRef.current.some((pipeline) =>
          ['building', 'pending', 'deploying'].includes(pipeline.status)
        )
      ) {
        fetchPipelines();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [supabase]);

  const fetchPipelines = async () => {
    if (cloudMode === 'cloud') {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (token) {
        const response = await fetch('/api/pipelines', {
          headers: new Headers({
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          }),
        });
        const json = await response.json();
        setPipelines(json['pipelines']);
      }
    } else {
      const response = await fetch('/api/local_pipelines', {
        headers: new Headers({
          'Content-Type': 'application/json',
        }),
      });
      const json = await response.json();
      setPipelines(json['pipelines']);
    }
  };

  return (
    <div className={styles.container}>
      <Image
        alt={`sciphi.png`}
        src={`/images/sciphi.png`}
        width={48}
        height={48}
        className={styles.logo}
      />
      <div className={styles.divider}></div>

      <div className={styles.userPanel}>
        <div className={styles.currentWorkspace}>
          <div>
            <Image
              src="/images/dummy_logo.png"
              alt="Acme Co."
              width="30"
              height="30"
              className={styles.workspaceIcon}
            />
          </div>
          Acme Co.
        </div>
      </div>

      <div className={styles.divider}></div>
      <div className={styles.userPanel}>
        <Menu as="div" className="relative inline-block text-left">
          <div>
            <Menu.Button className="inline-flex w-full justify-center gap-x-1.5 rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
              {pipeline?.name || 'Select Pipeline'}
              <ChevronDownIcon
                className="-mr-1 h-5 w-5 text-gray-400"
                aria-hidden="true"
              />
            </Menu.Button>
          </div>

          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="py-1">
                {pipelines.map((pipeline) => (
                  <Menu.Item key={pipeline.id}>
                    {({ active }) => (
                      <Link
                        href={
                          cloudMode === 'cloud'
                            ? `/pipeline/${pipeline.id}`
                            : `/pipeline/${pipeline.id}/local_pipeline`
                        }
                        className={`${styles.menuItem} ${
                          active ? 'bg-gray-100 text-gray-900' : 'text-gray-700'
                        } block px-4 py-2 text-sm`}
                      >
                        {pipeline.name}
                      </Link>
                    )}
                  </Menu.Item>
                ))}
              </div>
            </Menu.Items>
          </Transition>
        </Menu>
      </div>
    </div>
  );
}

export { WorkspacesSelect };
