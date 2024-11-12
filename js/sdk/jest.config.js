module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  testRunner: 'jest-circus/runner',
  maxWorkers: 1,
  testMatch: [
    "**/__tests__/**/*.ts?(x)",
    "**/__tests__/**/?(*.)+(spec|test).ts?(x)",
  ],
};
