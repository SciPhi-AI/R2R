import dynamic from 'next/dynamic';
import { theme } from 'redark-theme';

const Redoc = dynamic(
  () => import('redoc').then((module) => module.RedocStandalone),
  { ssr: false }
);

const App = () => <Redoc specUrl="/swagger.json" options={{ theme: theme }} />;

export default App;