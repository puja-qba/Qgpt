import logging
import os


class Logger:

    @staticmethod
    def get_logger():

        if not os.path.exists("logs"):
            os.makedirs("logs")

        logging.basicConfig(
            filename="logs/framework.log",
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

        return logging.getLogger()
