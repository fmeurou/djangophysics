FROM python:3.9
ENV PYTHONUNBUFFERED 1
RUN apt update -y && apt upgrade -y
RUN apt install -y supervisor
RUN groupadd apps
RUN mkdir /var/apps /var/apps/bin /var/apps/packages /var/apps/media /var/apps/static /var/log/physics
RUN useradd -g apps -s /bin/bash -d /var/apps apps
WORKDIR /var/apps
COPY config/requirements.txt /var/apps/
RUN pip install --upgrade djangophysics
RUN pip install -r requirements.txt
RUN django-admin startproject api
RUN cp /usr/local/lib/python3.9/site-packages/djangophysics/settings.example.py /var/apps/api/settings.py
COPY config/local.py /var/apps/api/local.py
# TODO: fix path issue on gunicorn
RUN cp /usr/local/lib/python3.9/site-packages/djangophysics/settings.example.py /var/apps/api/api/settings.py
COPY config/local.py /var/apps/api/api/local.py
RUN cp /usr/local/lib/python3.9/site-packages/djangophysics/urls.example.py /var/apps/api/urls.py
COPY config/supervisor.conf /etc/supervisor/supervisor.conf
COPY config/api.conf /etc/supervisor/conf.d/api.conf
COPY scripts/gunicorn_start.sh /var/apps/bin/gunicorn_start.sh
RUN chmod +x /var/apps/bin/gunicorn_start.sh
RUN chown -R apps:apps /var/apps
RUN chown -R apps:apps /var/log/physics
USER apps
RUN python /var/apps/api/manage.py collectstatic
USER root
