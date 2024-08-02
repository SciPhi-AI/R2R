import { useState, useEffect } from 'react';

import { Switch } from '@/components/ui/switch';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { SingleSwitchProps } from '@/types';

const SingleSwitch: React.FC<SingleSwitchProps> = ({
  id,
  initialChecked,
  onChange,
  label,
  tooltipText,
}) => {
  const [isChecked, setIsChecked] = useState(initialChecked);

  useEffect(() => {
    setIsChecked(initialChecked);
  }, [initialChecked]);

  const handleSwitchChange = (checked: boolean) => {
    setIsChecked(checked);
    onChange(id, checked);
  };

  return (
    <div className="flex justify-between items-center mt-4">
      {label && (
        <label htmlFor={id} className="mr-2 text-sm font-medium text-zinc-300">
          {label}
        </label>
      )}
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>
            <Switch
              id={id}
              checked={isChecked}
              onCheckedChange={handleSwitchChange}
            />
          </TooltipTrigger>
          <TooltipContent>
            <p>{tooltipText}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
};

export default SingleSwitch;
