# -*- coding: utf-8 -*-
# Regroup Django's specific function needed by the command line.

import datetime
import json


from django.db.models import Q

from aiida.common.datastructures import wf_states
from aiida.utils import timezone
from aiida.utils.logger import get_dblogger_extra

def get_group_list(user, type_string, n_days_ago=None,
                   name_filters={}):
    from aiida.orm.implementation.django.group import Group

    name_filters = {"name__" + k: v for (k, v) in name_filters.iteritems() if v}

    if n_days_ago:
        n_days_ago = timezone.now() - datetime.timedelta(days=n_days_ago)

    groups = Group.query(user=user, type_string=type_string,
                         past_days=n_days_ago,
                         **name_filters)

    return tuple([
        (str(g.pk), g.name, len(g.nodes), g.user.email.strip(), g.description)
        for g in groups
    ])

def get_workflow_list(pk_list=[], user=None, all_states=False, n_days_ago=None):
    """
    Get a list of workflow.
    """

    from aiida.backends.djsite.db.models import DbWorkflow

    if pk_list:
        filters = Q(pk__in=pk_list)
    else:
        filters = Q(user=user)

        if not all_states:
            filters &= Q(state=wf_states.FINISHED) & Q(state=wf_states.ERROR)
        if n_days_ago:
            t = timezone.now() - datetime.timedelta(days=n_days_ago)
            filters &= Q(ctime__gte=t)

    wf_list = DbWorkflow.objects.filter(filters).order_by('ctime')

    return wf_list

def get_log_messages(obj):
    """
    Get the log messages for the object.
    """
    from aiida.backends.djsite.db.models import DbLog
    extra = get_dblogger_extra(obj)
    # convert to list, too
    log_messages = list(DbLog.objects.filter(**extra).order_by('time').values(
        'loggername', 'levelname', 'message', 'metadata', 'time'))

    # deserialize metadata
    for log in log_messages:
        log.update({'metadata': json.loads(log['metadata'])})

    return log_messages

def get_valid_job_calculation(user=None, pk_list=[], n_days_after=None,
                              n_days_before=None, computers=None):
    """
    Get a list of valid job calculation from the user.

    Currently, this also select the associated computer with it.
    """

    from aiida.orm.calculation.job import JobCalculation
    from aiida.backends.djsite.db.models import DbAttribute

    valid_states = [calc_states.FINISHED, calc_states.RETRIEVALFAILED,
                    calc_states.PARSINGFAILED, calc_states.FAILED]

    attributes_filter = DbAttribute.objects.filter(key='state',
                                                          tval__in=valid_states)
    # NOTE: IMPORTED state is not a dbattribute so won't be filtered out
    # at this stage, but this case should be sorted out later when we try
    # to access the remote_folder (if directory is not accessible, we skip)

    filters = Q(user=user) & Q(dbattributes_in=attributes_filter)

    if pk_list:
        fitlers &= Q(pk__in=pk_list)
    else:
        # Filter user, day, older_than, computer name
        if n_days_ago is not None:
            t = timezone.now() - datetime.timedelta(days=n_days_after)
            filters &= Q(mtime__gte=t)

        if older_than is not None:
            t = timezone.now() - datetime.timedelta(days=n_days_before)
            filters &= Q(mtime__lte=n_days_before)

        if computers is not None:
            filters &= Q(dbcomputer__namme__in=computers)

    calculations = (JobCalculation.query(filters)
                    .distinct().order_by('mtime')
                    .select_related("dbcomputer"))

    return calculations


def get_computers_work_dir(calculations, user):
    """
    Get a list of computers and their remotes working directory.

   `calculations` should be a list of JobCalculation object.
    """

    from aiida.orm.computer import Computer
    from aiida.execmanager import get_authinfo

    computers = [Computer.get(c.dbcomputer) for c in calculations]

    remotes = {}
    for computer in computers:
        remotes[computer.name] = {
            'transport': get_authinfo(computer=computer, aiidauser=user).get_transport(),
            'computer': computer,
        }

    return remotes


