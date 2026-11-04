FROM odoo:20

USER root

# legacy tz names (GB, US/Eastern...) moved out of tzdata; pytz needs them on db create
RUN apt-get update && apt-get install -y --no-install-recommends tzdata-legacy && rm -rf /var/lib/apt/lists/*

# Install production dependencies
ADD requirements.txt /mnt/requirements.txt
RUN pip3 install --no-cache-dir --ignore-requires-python --break-system-packages --ignore-installed -r /mnt/requirements.txt

USER odoo

# Setup Odoo
ADD --chown=odoo:odoo additional-addons /mnt/additional-addons
ADD --chown=odoo:odoo addons /mnt/addons
ADD --chown=odoo:odoo odoo.conf /etc/odoo/odoo.conf
