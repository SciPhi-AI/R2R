module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  testMatch: [
    "**/__tests__/**/*.ts?(x)",
    "**/__tests__/**/?(*.)+(spec|test).ts?(x)",
  ],
  maxWorkers: 1,
};
