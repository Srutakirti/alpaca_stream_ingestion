import logging
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable
import yaml

# --- Configuration ---
# 1. Kafka bootstrap servers. Replace with your Kafka broker(s).
KAFKA_BOOTSTRAP_SERVERS = ['192.168.49.2:32100']

# 2. The name of the topic you want to create.
#TOPIC_NAME = 'iex-topic-1-flattened'
TOPIC_NAME = 'iex-topic-1'

with open('config/config.yaml', 'r') as file:
    config = yaml.safe_load(file)
    topic_map = config.get('kafka', {}).get('topics', {})

# 3. The number of partitions for the new topic.
# A good starting point is to match the number of consumers you expect.
NUM_PARTITIONS = 3

# 4. The replication factor for the new topic.
# This should be less than or equal to the number of brokers in your cluster.
# For a single-broker setup (like a local test environment), this must be 1.
REPLICATION_FACTOR = 1

logging.getLogger('kafka').setLevel(logging.WARNING)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def create_topic(TOPIC_LIST):
    """
    Connects to Kafka and creates a new topic based on the configuration.
    """
    admin_client = None
    try:
        # Initialize the KafkaAdminClient
        admin_client = KafkaAdminClient(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            client_id='kafka_topic_creator'
        )
        logging.info("Successfully connected to Kafka brokers.")

        topic_objs = []
        for TOPIC_NAME in TOPIC_LIST:
        # Define the new topic with its configuration
            topic = NewTopic(
                name=TOPIC_NAME,
                num_partitions=NUM_PARTITIONS,
                replication_factor=REPLICATION_FACTOR
            )
            topic_objs.append(topic)

        # Call the create_topics API
        # The create_topics method expects a list of NewTopic objects.
        logging.info(f"Attempting to create topics '{TOPIC_LIST}'...")
        resp = admin_client.create_topics(new_topics=topic_objs, validate_only=False)
        logging.info(f"Topics created in {TOPIC_LIST}")

        
        




    except TopicAlreadyExistsError:
        logging.warning(f"Topic '{TOPIC_LIST}' already exists. No action taken.")
    except NoBrokersAvailable:
        logging.error(f"Could not connect to any Kafka brokers at {KAFKA_BOOTSTRAP_SERVERS}. Please check the address and ensure Kafka is running.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        # Ensure the admin client is closed
        if admin_client:
            admin_client.close()
            logging.info("Kafka admin client closed.")


if __name__ == "__main__":
    create_topic(list(topic_map.values()))