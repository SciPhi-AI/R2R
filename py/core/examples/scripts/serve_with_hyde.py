import fire

from r2r import R2RBuilder, R2RConfig, R2RPipeFactoryWithMultiSearch


def main(task_prompt_name="hyde"):
    # Load the default configuration file
    config = R2RConfig.from_toml()

    app = (
        R2RBuilder(config)
        .with_pipe_factory(R2RPipeFactoryWithMultiSearch)
        .build(
            # Add optional override arguments which propagate to the pipe factory
            task_prompt_name=task_prompt_name,
        )
    )
    app.serve()


if __name__ == "__main__":
    fire.Fire(main)
