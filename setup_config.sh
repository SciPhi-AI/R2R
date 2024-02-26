#!/bin/bash

# ANSI Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

update_env_example() {
    local db_choice=$1
    local integrate_websearch=$2
    local tmp_file=$(mktemp)

    # Define patterns to match based on the database choice
    local pattern_to_comment=""
    local pattern_to_uncomment=""
    if [ "$db_choice" = "1" ]; then
        # If pg_vector is chosen, comment out QDRANT keys and uncomment PGVECTOR keys
        pattern_to_comment="^QDRANT_"
        pattern_to_uncomment="^#PGVECTOR_"
    elif [ "$db_choice" = "2" ]; then
        # If qdrant is chosen, comment out PGVECTOR keys
        pattern_to_comment="^POSTGRES_"
    fi

    # Comment out the lines matching the pattern for the database choice
    if [ ! -z "$pattern_to_comment" ]; then
        sed "/$pattern_to_comment/s/^/#/" .env.example > "$tmp_file" && mv "$tmp_file" .env.example
    fi

    # Uncomment the lines matching the pattern for the database choice
    if [ ! -z "$pattern_to_uncomment" ]; then
        sed "/$pattern_to_uncomment/s/^#//" .env.example > "$tmp_file" && mv "$tmp_file" .env.example
    fi

    # Handle SERPER_API_KEY based on websearch integration choice
    if [ "$integrate_websearch" != "yes" ] && [ "$integrate_websearch" != "y" ] && [ "$integrate_websearch" != "Y" ] && [ "$integrate_websearch" != "1" ]; then
        # Comment out SERPER_API_KEY if websearch integration is not chosen
        sed -i '/^SERPER_API_KEY/s/^/#/' .env.example
    else
        # Uncomment SERPER_API_KEY if websearch integration is chosen
        sed -i '/^#SERPER_API_KEY/s/^#//' .env.example
    fi
}

# Function to update config.json
update_config() {
    jq "$1" config.json > config.tmp && mv config.tmp config.json
}

# Function to prompt and read user choice with retry mechanism
prompt_with_retry() {
    local prompt_message="$1"
    local user_choice_var=$2 # Changed to store the variable name as a string
    local attempt=0
    local max_attempts=2

    while [ $attempt -lt $max_attempts ]; do
        echo -e "$prompt_message"
        read user_input
        eval $user_choice_var="'$user_input'" # Indirectly assign the input to the variable
        case ${!user_choice_var} in # Use indirect reference to check the value
            1|2|y|Y|yes|YES|n|N|no|NO)
                return 0
                ;;
            *)
                let attempt++
                echo "Invalid choice. Please try again."
                if [ $attempt -eq $max_attempts ]; then
                    echo "Failed too many times. Exiting."
                    exit 1
                fi
                ;;
        esac
    done
}

echo "Setting up your R2R configuration..." 
echo -e "Default options are displayed in ${GREEN}Green${NC}"
echo -e "\n"

# Select vector database provider
prompt_message="Select your vector database provider:\n1) ${GREEN}pg_vector (Supabase)${NC} | 2) qdrant\n\nEnter choice [1-2]: "
prompt_with_retry "$prompt_message" db_choice

case $db_choice in
    1)
        update_config '.database.provider = "pg_vector"'
        echo "Make sure the vectors extension plugin has been enabled in your PostgreSQL."
        #echo -e "Make sure the ${YELLOW}vector${NC} extension plugin has been enabled in ${GREEN}Supabase ${NC} > ${YELLOW}Project > Database > Extensions${NC}."
        ;;
    2)
        update_config '.database.provider = "qdrant"'
        ;;
esac

# Call update_env_example with the user's database 
echo -e "\n"
prompt_message="Do you want to integrate with websearch?\n1) ${GREEN}no${NC} | 2) yes\n\nEnter choice [1-2]: "
prompt_with_retry "$prompt_message" integrate_websearch

case "$integrate_websearch" in
    [yY] | [yY][eE][sS] | [1] )
        echo "Websearch integration will be enabled."
        ;;
    [nN] | [nN][oO] | [2] )
        echo "Websearch integration will not be enabled."
        sed -i '/^SERPER_API_KEY/s/^/#/' .env.example
        ;;
esac

update_env_example $db_choice $integrate_websearch

# Select embedding provider (OpenAI for now)
update_config '.embedding.provider = "openai"'

# Select model
echo -e "\n"
echo "Select the OpenAI model for embedding. Each model has different characteristics suitable for various use cases."
echo "Consider the dimensions, batch size, and pricing when making your choice:"
echo -e "\n"

echo -e "${GREEN}1) text-embedding-3-small:${NC}"
echo -e "\t- Use case: Suitable for general-purpose embedding tasks with efficient processing."
echo -e "\t- Dimensions: 1536"
echo -e "\t- Recommended batch size: 32"
echo -e "\t- Pricing: Approximately 62,500 pages per dollar. High efficiency and cost-effective for large-scale applications."
echo -e "\n"

echo -e "2) text-embedding-3-large"
echo -e "\t- Use case: Ideal for tasks requiring high-quality embeddings, such as semantic search or complex text similarity."
echo -e "\t- Dimensions: 4096"
echo -e "\t- Recommended batch size: 16"
echo -e "\t- Pricing: Approximately 9,615 pages per dollar. Offers superior performance at a higher cost."
echo -e "\n"

echo -e "3) text-embedding-ada-002"
echo -e "\t- Use case: A balanced option for tasks needing a compromise between quality and efficiency."
echo -e "\t- Dimensions: 2048"
echo -e "\t- Recommended batch size: 24"
echo -e "\t- Pricing: Approximately 12,500 pages per dollar. Balances cost and performance effectively."
echo -e "\n"

prompt_message="Enter choice [1-3]: "
prompt_with_retry "$prompt_message" model_choice

case $model_choice in
    1)
        update_config '.embedding.model = "text-embedding-3-small"'
        ;;
    2)
        update_config '.embedding.model = "text-embedding-3-large"'
        ;;
    3)
        update_config '.embedding.model = "text-embedding-ada-002"'
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo "Would you like to use the recommended default sizes for the model or specify custom values?"
echo -e "1) Use ${GREEN}default sizes${NC}"
echo "2) Specify custom values"
prompt_message="Enter choice [1-2]: "
prompt_with_retry "$prompt_message" size_choice
echo -e "\n"

if [ "$size_choice" = "1" ]; then
    case $model_choice in
        1)
            update_config '.embedding.dimension = 1536'
            update_config '.embedding.batch_size = 32'
            ;;
        2)
            update_config '.embedding.dimension = 4096'
            update_config '.embedding.batch_size = 16'
            ;;
        3)
            update_config '.embedding.dimension = 2048'
            update_config '.embedding.batch_size = 24'
            ;;
    esac
elif [ "$size_choice" = "2" ]; then
    echo "Select the dimension (trade-offs below):"
    echo -e "1) 1536 - Efficient, cost-effective, suitable for general tasks. Less detail."
    echo -e "2) 2048 - Balanced, moderate detail and efficiency."
    echo -e "3) 4096 - High detail, better for complex tasks. More compute, slower, higher cost."
    echo "Other) Type custom dimension"
    echo -e "\n"
    prompt_message="Enter choice [1-3] or type it: "
    prompt_with_retry "$prompt_message" dimension_choice
    
    case $dimension_choice in
        1)
            custom_dimension=1536
            ;;
        2)
            custom_dimension=2048
            ;;
        3)
            custom_dimension=4096
            ;;
        *)
            echo "Invalid choice. Exiting."
            exit 1
            ;;
    esac
    update_config ".embedding.dimension = $custom_dimension"
    
    echo "Select the batch size (consider processing speed and cost):"
    echo "1) 16 - Suitable for high-quality embeddings with slower processing and higher cost."
    echo "2) 24 - A balanced choice for moderate processing speed and cost."
    echo "3) 32 - Fastest processing, most cost-effective, but may reduce embedding quality."
    echo "Other) Type custom batch size"
    echo -e "\n"
    prompt_message="Enter choice [1-3] or type it: "
    prompt_with_retry "$prompt_message" batch_size_choice
    
    case $batch_size_choice in
        1)
            custom_batch_size=16
            ;;
        2)
            custom_batch_size=24
            ;;
        3)
            custom_batch_size=32
            ;;
        *)
            echo "Invalid choice. Exiting."
            exit 1
            ;;
    esac
    update_config ".embedding.batch_size = $custom_batch_size"
fi

echo "Configuration setup is complete."
echo "Updating files..."

# Simple progress animation
for i in {1..100}; do
    sleep 0.001 

    num_equals=$((i / 2))

    bar=$(printf "%-${num_equals}s" "=")
    # Replace spaces with equals signs
    bar=${bar// /=}
    printf "\r0 %% [%-50s] %3d%%" "$bar" "$i"
done
echo -e "\n"
echo -e "\nFiles updated: ${YELLOW}.env.example${NC} and ${YELLOW}config.json${NC}. For a the full list of set up options modify ${YELLOW}config.json${NC} directly."
