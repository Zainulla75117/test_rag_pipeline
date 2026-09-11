import os
from dotenv import load_dotenv

load_dotenv()


def get_embedding_model():
    """Return the configured embedding model instance.

    Reads EMBEDDING_PROVIDER from .env:
      - "gemini" (default): GoogleGenerativeAIEmbeddings with gemini-embedding-2
      - "titan": BedrockEmbeddings with Amazon Titan Text Embeddings V2
    """
    provider = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()

    if provider == "titan":
        from langchain_aws import BedrockEmbeddings

        region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        dimensions = int(os.getenv("TITAN_EMBED_DIMENSIONS", "1024"))
        return BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v2:0",
            region_name=region,
            model_kwargs={"dimensions": dimensions, "normalize": True},
        )
    else:
        # Default: Gemini
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
