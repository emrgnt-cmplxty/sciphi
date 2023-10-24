"""A module which facilitates data augmentation.""" ""
import json
import logging
import os
from typing import Optional

import dotenv
import fire
from datasets import load_dataset
from tqdm import tqdm

from sciphi.core import JsonlDataWriter, LLMProviderName, Prompt
from sciphi.core.utils import get_config_dir
from sciphi.interface import LLMInterface, LLMInterfaceManager

# Load environment variables
dotenv.load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SHUFFLE_SEED = 42
DEFAULT_USER_INPUTS = {
    "user_supplied_suffix": "_Note_ - Ensure all question and answer pairs are implied by the context above.",
}


def get_output_path(output_dir: str, output_name: str) -> str:
    """Returns the complete path where the output will be saved."""
    return (
        os.path.join(output_dir, output_name)
        if os.path.isabs(output_dir)
        else os.path.join(os.getcwd(), output_dir, output_name)
    )


def ensure_directory_exists(filepath: str):
    """Ensures the directory of the given filepath exists."""
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory)


def augment_data_with_llm(
    entry: dict,
    prompt: Prompt,
    llm_interface: LLMInterface,
    user_supplied_inputs: dict[str, str],
):
    """Fetches augmented data from LLM for a given entry."""
    formatted_prompt = prompt.format(
        dataset_entry=entry, **user_supplied_inputs
    )
    return llm_interface.get_completion(formatted_prompt)


def get_output_path(output_dir: str, output_name: str) -> str:
    """Returns the complete path where the output will be saved."""
    return (
        os.path.join(output_dir, output_name)
        if os.path.isabs(output_dir)
        else os.path.join(os.getcwd(), output_dir, output_name)
    )


def ensure_directory_exists(filepath: str):
    """Ensures the directory of the given filepath exists."""
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory)


def augment_data_with_llm(
    entry: dict,
    prompt: Prompt,
    llm_interface: LLMInterface,
    user_supplied_inputs: dict[str, str],
):
    """Fetches augmented data from LLM for a given entry."""
    formatted_prompt = prompt.format(
        dataset_entry=entry, **user_supplied_inputs
    )
    return llm_interface.get_completion(formatted_prompt)


def main(
    # Run Settings
    output_dir="augmented_output",
    output_name=None,
    shuffle: bool = True,
    n_samples: int = 100,
    # LLM Settings
    llm_provider_name: str = "openai",
    llm_model_name: str = "gpt-3.5-turbo",
    llm_max_tokens_to_sample: str = 32,
    llm_temperature: float = 0.1,
    llm_top_k: int = 100,
    # Dataset Settings
    dataset_name: str = "ContextualAI/tiny-wiki100-chunks",
    dataset_split: str = "train",
    # Prompt Settings
    config_name: Optional[str] = "question_and_answer",
    config_path: Optional[str] = None,
    ## Additional user inputs (like user_supplied_suffix)
    ## can be passed in through Fire as kwargs, e.g.
    ## --user_supplied_inputs "{'your_input': 'Your Input Value'}"
    user_supplied_inputs: Optional[dict] = None,
    **kwargs,
):
    """Run the data augmenter."""

    # Validate configurations
    if config_name and config_path:
        raise ValueError(
            "Must provide either a config name or a config path, but not both."
        )
    # Initialize configuration and output path
    config_path_from_name_or_default = config_path or os.path.join(
        get_config_dir(), "prompts", f"{config_name}.yaml"
    )
    prompt = Prompt(config_path=config_path_from_name_or_default)
    config_name = config_path_from_name_or_default.split(os.path.sep)[
        -1
    ].replace(".yaml", "")
    output_name = (
        output_name
        or f"config_name__{config_name}_dataset_name__{dataset_name.replace('/','_')}.jsonl"
    )
    logger.info(
        f"Augmenting dataset {dataset_name} with prompt {config_name}."
    )
    logger.info(f"Saving the output to {output_name}.")
    output_path = get_output_path(output_dir, output_name)

    # Ensure output directory exists
    ensure_directory_exists(output_path)
    writer = JsonlDataWriter(output_path)

    dataset = load_dataset(dataset_name)
    llm_interface = LLMInterfaceManager.get_interface_from_args(
        provider_name=LLMProviderName(llm_provider_name),
        model_name=llm_model_name,
        # Additional args
        max_tokens_to_sample=llm_max_tokens_to_sample,
        temperature=llm_temperature,
        top_k=llm_top_k,
        # Used for re-routing requests to a remote vLLM server
        server_base=kwargs.get("llm_server_base", None),
    )

    dataset_split = dataset[dataset_split]
    if shuffle:
        dataset_split = dataset_split.shuffle(seed=SHUFFLE_SEED)
    n_samples = min(n_samples, len(dataset_split))
    samples = dataset_split.select(range(n_samples))
    if not user_supplied_inputs:
        user_supplied_inputs = DEFAULT_USER_INPUTS

    logger.info(f"Now running over {n_samples} samples.")
    for entry in tqdm(samples):
        formatted_prompt = prompt.format(
            dataset_entry=entry, **user_supplied_inputs
        )
        completion = llm_interface.get_completion(formatted_prompt)
        try:
            data = json.loads(completion)
            writer.write(data)
        except json.decoder.JSONDecodeError:
            logger.error(
                f"Failed to decode JSON response from LLM: {completion}"
            )


if __name__ == "__main__":
    fire.Fire(main)
