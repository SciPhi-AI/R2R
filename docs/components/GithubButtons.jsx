import React, { useEffect } from 'react';

const GithubButtons = () => {
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://buttons.github.io/buttons.js';
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);

    return () => {
      document.body.removeChild(script);
    };
  }, []);

  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: '10px' }}>
      <a
        className="github-button"
        href="https://github.com/SciPhi-AI/R2R"
        data-show-count="true"
        data-size="large"
        aria-label="Star"
      >
        Star
      </a>
      <a
        className="github-button"
        href="https://github.com/SciPhi-AI/R2R/subscription"
        data-icon="octicon-eye"
        data-size="large"
        aria-label="Watch"
      >
        Watch
      </a>
      <a
        className="github-button"
        href="https://github.com/SciPhi-AI/R2R/fork"
        data-icon="octicon-repo-forked"
        data-size="large"
        aria-label="Fork"
      >
        Fork
      </a>
    </div>
  );
};

export default GithubButtons;
