import { Button } from '@/components/ui/Button';

type WatchButtonProps = {
  isLoading: boolean;
  isPipelineNameValid: boolean;
  isDeploymentUrlValid: boolean;
  onClick: () => void;
};

function WatchButton({
  isLoading,
  isPipelineNameValid,
  isDeploymentUrlValid,
  onClick,
}: WatchButtonProps) {
  const isDisabled = !isPipelineNameValid || !isDeploymentUrlValid || isLoading;

  return (
    <Button
      onClick={onClick}
      className={`w-1/3 h-8 py-1 ${isDisabled ? 'cursor-not-allowed' : ''}`}
      variant="primary"
      disabled={isDisabled}
    >
      {isLoading ? 'Watching...' : 'Watch'}
    </Button>
  );
}

export { WatchButton };
