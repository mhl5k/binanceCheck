 
FROM ubuntu:latest
RUN apt-get update -y
RUN apt-get install python3 python3-pip -y
COPY *.txt .
RUN pip3 install requests -r requirements.txt
COPY *.py .
COPY *.json .
COPY *.md .
CMD python3 binanceCheck.py
