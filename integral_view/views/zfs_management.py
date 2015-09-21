import django, django.template

import integralstor_common
import integralstor_unicell
from integralstor_common import zfs, audit, ramdisk,file_processing
from integralstor_common import scheduler_utils
from integralstor_unicell import nfs,local_users

import json, time, os, shutil, tempfile, os.path, re, subprocess, sys, shutil, pwd, grp, stat,datetime

import integral_view
from integral_view.forms import zfs_forms,common_forms
  
def view_zfs_pools(request):
  return_dict = {}
  try:
    template = "view_zfs_pools.html"
    pool_list, err = zfs.get_pools()
    if err:
      raise Exception(err)
  
    if "action" in request.GET:
      if request.GET["action"] == "saved":
        conf = "ZFS pool information successfully updated"
      elif request.GET["action"] == "created_pool":
        conf = "ZFS pool successfully created"
      elif request.GET["action"] == "set_permissions":
        conf = "Directory ownership/permissions successfully set"
      elif request.GET["action"] == "created_dataset":
        conf = "ZFS dataset successfully created"
      elif request.GET["action"] == "created_zvol":
        conf = "ZFS block device volume successfully created"
      elif request.GET["action"] == "pool_deleted":
        conf = "ZFS pool successfully destroyed"
      elif request.GET["action"] == "pool_scrub_initiated":
        conf = "ZFS pool scrub successfully initiated"
      elif request.GET["action"] == "dataset_deleted":
        conf = "ZFS dataset successfully destroyed"
      elif request.GET["action"] == "zvol_deleted":
        conf = "ZFS block device volume successfully destroyed"
      elif request.GET["action"] == "slog_deleted":
        conf = "ZFS write cache successfully removed"
      elif request.GET["action"] == "changed_slog":
        conf = "ZFS pool write cache successfully set"
      return_dict["conf"] = conf
    return_dict["pool_list"] = pool_list
    return django.shortcuts.render_to_response(template, return_dict, context_instance = django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'ZFS pools'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error loading ZFS pools'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def view_zfs_pool(request):
  return_dict = {}
  try:
    template = 'logged_in_error.html'
    if 'name' not in request.REQUEST:
      raise Exception("No pool specified.")
    
    pool_name = request.REQUEST['name']
    pool, err = zfs.get_pool(pool_name)
    #print pool.keys()

    if err:
      raise Exception(err)
    elif not pool:
      raise Exception("Specified pool not found")

    snap_list, err = zfs.get_snapshots(pool_name)
    if err:
      raise Exception(err)

    return_dict['snap_list'] = snap_list
    return_dict['pool'] = pool
    return_dict['pool_name'] = pool_name
      
    template = "view_zfs_pool.html"
    return django.shortcuts.render_to_response(template, return_dict, context_instance = django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'ZFS pool details'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error loading ZFS pool details'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))


def create_zfs_pool(request):
  return_dict = {}
  try:

    free_disks, err = zfs.get_free_disks()
    if err:
      raise Exception(err)

    if not free_disks or len(free_disks) < 2:
      raise Exception('There are insufficient unused disks available to create a pool')

    pool_types = []
    if len(free_disks) >= 2 :
      pool_types.append('mirror')
    if len(free_disks) >= 3 :
      pool_types.append('raid5')
    if len(free_disks) >= 4 :
      pool_types.append('raid6')
      pool_types.append('raid10')

    if request.method == "GET":
      #Return the conf page
      form = zfs_forms.CreatePoolForm(pool_types = pool_types, num_free_disks = len(free_disks), initial={'num_disks': len(free_disks)})
      return_dict['form'] = form
      return_dict['num_disks'] = len(free_disks)
      return django.shortcuts.render_to_response("create_zfs_pool.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = zfs_forms.CreatePoolForm(request.POST, pool_types = pool_types, num_free_disks = len(free_disks))
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("create_zfs_pool.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      vdev_list = None
      if cd['pool_type'] in ['raid5', 'raid6']:
        vdev_list, err = zfs.create_pool_data_vdev_list(cd['pool_type'], cd['num_raid_disks'])
      elif cd['pool_type'] == 'raid10':
        vdev_list, err = zfs.create_pool_data_vdev_list(cd['pool_type'], stripe_width = cd['stripe_width'])
      else:
        vdev_list, err = zfs.create_pool_data_vdev_list(cd['pool_type'])
      if err:
        raise Exception(err)
      #print 'vdevlist', vdev_list
      result, err = zfs.create_pool(cd['name'], cd['pool_type'], vdev_list)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Created a ZFS pool named %s of type %s"%(cd['name'], cd['pool_type'])
      audit.audit("create_zfs_pool", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_pools?action=created_pool')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'ZFS pool creation'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error creating a ZFS pool'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def scrub_zfs_pool(request):

  return_dict = {}
  try:
    if 'name' not in request.REQUEST:
      raise Exception("No pool specified. Please use the menus")
    name = request.REQUEST["name"]
    return_dict["name"] = name
    if request.method == "GET":
      #Return the conf page
      return django.shortcuts.render_to_response("scrub_zfs_pool_conf.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      result, err = zfs.scrub_pool(name)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "ZFS pool scrub initiated on pool %s"%name
      audit.audit("scrub_zfs_pool", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_pools?action=pool_scrub_initiated')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'ZFS pool scrub'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error scrubbing ZFS pool'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def delete_zfs_pool(request):

  return_dict = {}
  try:
    if 'name' not in request.REQUEST:
      raise Exception("No pool specified. Please use the menus")
    name = request.REQUEST["name"]
    return_dict["name"] = name
    if request.method == "GET":
      #Return the conf page
      return django.shortcuts.render_to_response("delete_zfs_pool_conf.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      result, err = zfs.delete_pool(name)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Deleted ZFS pool %s"%name
      audit.audit("delete_zfs_pool", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_pools?action=pool_deleted')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Remove a ZFS pool'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error removing a ZFS pool'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def set_zfs_slog(request):
  return_dict = {}
  try:
    
    template = 'logged_in_error.html'

    if 'pool' not in request.REQUEST:
      raise Exception("No pool specified.")

    pool_name = request.REQUEST["pool"]

    pool, err = zfs.get_pool(pool_name)

    if err:
      raise Exception(err)
    elif not pool:
      raise Exception("Error loading ZFS storage information : Specified pool not found")

    slog = None
    if not pool['config']['logs']:
      slog = None
    else:
      kids = pool['config']['logs']['root']['children']
      if len(kids) == 1 and 'ramdisk' in kids[0]:
        slog = 'ramdisk'
        rdisk, err = ramdisk.get_ramdisk_info('/mnt/ramdisk_%s'%pool_name)
        if err:
          raise Exception(err)
        elif not rdisk:
          raise Exception("Could not determine the configuration for the RAM disk for the specified ZFS pool")
        ramdisk_size = rdisk['size']/1024
      else:
        #For now pass but we need to code this to read the component disk ID!!!!!!!!!!!!1
        slog = 'ssd'
        pass

    if request.method == "GET":
      #Return the conf page

      initial = {}
      initial['pool'] = pool_name
      initial['slog'] = slog
      if slog == 'ramdisk':
        initial['ramdisk_size'] = ramdisk_size

      form = zfs_forms.SlogForm(initial=initial)
      return_dict['form'] = form
      return django.shortcuts.render_to_response("edit_zfs_slog.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = zfs_forms.SlogForm(request.POST)
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("edit_zfs_slog.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      #print cd
      if cd['slog'] == 'ramdisk':
        if ((cd['slog'] == slog) and (cd['ramdisk_size'] != ramdisk_size)) or (cd['slog'] != slog):
          # Changed to ramdisk or ramdisk parameters changed so destroy and recreate
          oldramdisk, err = ramdisk.get_ramdisk_info('/mnt/ramdisk_%s'%cd['pool'])
          if err:
            raise Exception(err)
          if oldramdisk:
            result, err = ramdisk.destroy_ramdisk('/mnt/ramdisk_%s'%cd['pool'], cd['pool'])
            if err:
              raise Exception(err)
            result, err = zfs.remove_pool_vdev(cd['pool'], '/mnt/ramdisk_%s/ramfile'%cd['pool'])
            if err:
              raise Exception(err)
          result, err = ramdisk.create_ramdisk(1024*cd['ramdisk_size'], '/mnt/ramdisk_%s'%cd['pool'], cd['pool'])
          if err:
            raise Exception(err)
          else:
            result, err = zfs.set_pool_log_vdev(cd['pool'], '/mnt/ramdisk_%s/ramfile'%cd['pool'])
            if err:
              ramdisk.destroy_ramdisk('/mnt/ramdisk_%s'%cd['pool'], cd['pool'])
              raise Exception(err)
            audit.audit("edit_zfs_slog", 'Changed the write log for pool %s to a RAM disk of size %dGB'%(cd['pool'], cd['ramdisk_size']), request.META["REMOTE_ADDR"])
                
      return django.http.HttpResponseRedirect('/view_zfs_pools?action=changed_slog')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Set ZFS pool write cache'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error setting ZFS pool write cache'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def remove_zfs_slog(request):

  return_dict = {}
  try:
    if 'pool' not in request.REQUEST:
      raise Exception("No pool specified. Please use the menus")
    if 'device' not in request.REQUEST:
      raise Exception("No device specified. Please use the menus")
    pool = request.REQUEST["pool"]
    return_dict["pool"] = pool
    device = request.REQUEST["device"]
    return_dict["device"] = device
    if request.method == "GET":
      #Return the conf page
      return django.shortcuts.render_to_response("remove_zfs_slog_conf.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      result, err = zfs.remove_pool_vdev(pool, device)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
      result, err = ramdisk.destroy_ramdisk('/mnt/ramdisk_%s'%pool, pool)
      if err:
        raise Exception(err)
 
      audit_str = "Removed ZFS write cache RAM Disk for pool %s"%pool
      audit.audit("remove_zfs_slog", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_pools?action=slog_deleted')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Removing ZFS pool write cache'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error removing ZFS pool write cache'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def view_zfs_dataset(request):
  return_dict = {}
  try:
    template = 'logged_in_error.html'
    if 'name' not in request.REQUEST:
      raise Exception("No dataset specified.")
    
    dataset_name = request.REQUEST['name']
    if '/' in dataset_name:
      pos = dataset_name.find('/')
      pool = dataset_name[:pos]
    else:
      pool = dataset_name
    return_dict['pool'] = pool

    properties, err = zfs.get_properties(dataset_name)
    if err:
      raise Exception(err)
    elif not properties:
      raise Exception("Specified dataset not found")

    children, err = zfs.get_children_datasets(dataset_name)
    if err:
      raise Exception(err)

    if children:
      return_dict['children'] = children
    return_dict['name'] = dataset_name
    return_dict['properties'] = properties
    return_dict['exposed_properties'] = ['compression', 'compressratio', 'dedup',  'type', 'usedbychildren', 'usedbydataset', 'creation']
    if 'result' in request.GET:
      return_dict['result'] = request.GET['result']

    template = "view_zfs_dataset.html"
    return django.shortcuts.render_to_response(template, return_dict, context_instance = django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'ZFS dataset details'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error loading ZFS dataset details'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def edit_zfs_dataset(request):
  return_dict = {}
  try:
    if 'name' not in request.REQUEST:
      raise Exception('Dataset name not specified. Please use the menus.')
    name = request.REQUEST["name"]
    properties, err = zfs.get_properties(name)
    if not properties and err:
      raise Exception(err)
    elif not properties:
      raise Exception("Error loading ZFS dataset properties")

    if request.method == "GET":
      #Return the conf page
      initial = {}
      initial['name'] = name
      for p in ['compression', 'dedup', 'readonly']:
        if properties[p]['value'] == 'off':
          initial[p] = False
        else:
          initial[p] = True

      form = zfs_forms.DatasetForm(initial=initial)
      return_dict['form'] = form
      return django.shortcuts.render_to_response("edit_zfs_dataset.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = zfs_forms.DatasetForm(request.POST)
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("edit_zfs_dataset.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      result_str = ""
      audit_str = "Changed the following dataset properties for dataset %s : "%name
      success = False
      # Do this for all boolean values
      to_change = []
      for p in ['compression', 'dedup', 'readonly']:
        orig = properties[p]['value']
        if cd[p]:
          changed = 'on'
        else:
          changed = 'off'
        #print 'property %s orig %s changed %s'%(p, orig, changed)
        if orig != changed:
          result, err = zfs.set_property(name, p, changed)
          #print err
          if not result:
            result_str += ' Error setting property %s'%p
            if not err:
              results += ' : %s'%str(e)
          else:
            result_str += ' Successfully set property %s to %s'%(p, changed)
            audit_str += " property '%s' set to '%s'"%(p, changed)
            success = True
      if success:
        audit.audit("edit_zfs_dataset", audit_str, request.META["REMOTE_ADDR"])
                
 
      return django.http.HttpResponseRedirect('/view_zfs_dataset?name=%s&result=%s'%(name, result_str))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Modify ZFS dataset properties'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error modify ZFS dataset properties'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def delete_zfs_dataset(request):

  return_dict = {}
  try:
    if 'name' not in request.REQUEST:
      raise Exception("Error deleting ZFS dataset- No dataset specified. Please use the menus")
    if 'type' not in request.REQUEST:
      type = 'dataset'
    else:
      type = request.REQUEST['type']
    name = request.REQUEST["name"]
    return_dict["name"] = name
    return_dict["type"] = type
    if request.method == "GET":
      #Return the conf page
      return django.shortcuts.render_to_response("delete_zfs_dataset_conf.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      result, err = zfs.delete_dataset(name)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      if type == 'dataset':
        audit_str = "Deleted ZFS dataset %s"%name
        audit.audit("delete_zfs_dataset", audit_str, request.META["REMOTE_ADDR"])
        return django.http.HttpResponseRedirect('/view_zfs_pools?action=dataset_deleted')
      else:
        audit_str = "Deleted ZFS block device volume %s"%name
        audit.audit("delete_zfs_zvol", audit_str, request.META["REMOTE_ADDR"])
        return django.http.HttpResponseRedirect('/view_zfs_pools?action=zvol_deleted')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Remove a ZFS dataset/volume'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error removing a dataset/volume '
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def create_zfs_dataset(request):
  return_dict = {}
  try:
    if 'pool' not in request.REQUEST:
      raise Exception("No parent pool provided. Please use the menus.")
    pool = request.REQUEST['pool']
    datasets, err = zfs.get_children_datasets(pool)
    if err:
      raise Exception("Could not retrieve the list of existing datasets")
    if pool not in datasets:
      datasets.append(pool)
    return_dict['pool'] = pool

    if request.method == "GET":
      parent = None
      if 'parent' in request.GET:
        parent = request.GET['parent']
      #Return the conf page
      initial = {}
      if parent:
        initial['parent'] = parent
      initial['pool'] = pool
      form = zfs_forms.CreateDatasetForm(initial=initial, datasets = datasets)
      return_dict['form'] = form
      return django.shortcuts.render_to_response("create_zfs_dataset.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = zfs_forms.CreateDatasetForm(request.POST, datasets = datasets)
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("create_zfs_dataset.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      properties = {}
      if 'compression' in cd and cd['compression']:
        properties['compression'] = 'on'
      if 'dedup' in cd and cd['dedup']:
        properties['dedup'] = 'on'
      result, err = zfs.create_dataset(cd['parent'], cd['name'], properties)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Created a ZFS dataset named %s/%s"%(cd['parent'], cd['name'])
      audit.audit("create_zfs_dataset", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_pools?action=created_dataset')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Create a ZFS dataset'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error creating a ZFS dataset'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def create_zfs_zvol(request):
  return_dict = {}
  try:
    if 'pool' not in request.REQUEST:
      raise Exception("No parent pool provided. Please use the menus.")
    pool = request.REQUEST['pool']
    return_dict['pool'] = pool

    if request.method == "GET":
      parent = None
      if 'parent' in request.GET:
        parent = request.GET['parent']
      initial = {}
      initial['pool'] = pool
      form = zfs_forms.CreateZvolForm(initial=initial)
      return_dict['form'] = form
      return django.shortcuts.render_to_response("create_zfs_zvol.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = zfs_forms.CreateZvolForm(request.POST)
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("create_zfs_zvol.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      properties = {}
      if 'compression' in cd and cd['compression']:
        properties['compression'] = 'on'
      if 'dedup' in cd and cd['dedup']:
        properties['dedup'] = 'on'
      result, err = zfs.create_zvol(cd['pool'], cd['name'], properties, cd['size'], cd['unit'])
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Created a ZFS block device volume named %s/%s"%(cd['pool'], cd['name'])
      audit.audit("create_zfs_zvol", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_pools?action=created_zvol')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Create a ZFS block device volume'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error creating a ZFS block device volume '
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def view_zfs_zvol(request):
  return_dict = {}
  try:
    template = 'logged_in_error.html'
    if 'name' not in request.REQUEST:
      raise Exception("No block device volume specified.")
    
    name = request.REQUEST['name']
    if '/' in name:
      pos = name.find('/')
      pool = name[:pos]
    else:
      pool = name
    return_dict['pool'] = pool

    properties, err = zfs.get_properties(name)
    if not properties and err:
      raise Exception(err)
    elif not properties:
      raise Exception("Specified block device volume not found")

    return_dict['name'] = name
    return_dict['properties'] = properties
    return_dict['exposed_properties'] = ['compression', 'compressratio', 'dedup',  'type',  'creation']
    if 'result' in request.GET:
      return_dict['result'] = request.GET['result']

    template = "view_zfs_zvol.html"
    return django.shortcuts.render_to_response(template, return_dict, context_instance = django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'ZFS block device volume details'
    return_dict['tab'] = 'view_zfs_pools_tab'
    return_dict["error"] = 'Error loading ZFS block device volume details'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def view_zfs_snapshots(request):
  return_dict = {}
  try:
    template = 'logged_in_error.html'

    #If the list of snapshots is for a particular dataset or pool, get the name of that ds or pool
    name = None
    if 'name' in request.GET:
      name = request.GET['name']

    snap_list, err = zfs.get_snapshots(name)
    if err:
      raise Exception(err)

    if "action" in request.GET:
      conf = None
      if request.GET["action"] == "created":
        conf = "ZFS snapshot successfully created"
      elif request.GET["action"] == "deleted":
        conf = "ZFS snapshot successfully destroyed"
      elif request.GET["action"] == "renamed":
        conf = "ZFS snapshot successfully renamed"
      elif request.GET["action"] == "rolled_back":
        conf = "ZFS filesystem successfully rolled back to the snapshot"
      if conf:
        return_dict["conf"] = conf
    return_dict["snap_list"] = snap_list
    template = "view_zfs_snapshots.html"
    return django.shortcuts.render_to_response(template, return_dict, context_instance = django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'ZFS snapshots'
    return_dict['tab'] = 'view_zfs_snapshots_tab'
    return_dict["error"] = 'Error loading ZFS snapshots'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def create_zfs_snapshot(request):
  return_dict = {}
  try:
    datasets, err = zfs.get_all_datasets_and_pools()
    if not datasets:
      raise Exception("Could not get the list of existing datasets")

    if request.method == "GET":
      target = None
      if 'target' in request.GET:
        target = request.GET['target']
      #Return the conf page
      initial = {}
      if target:
        initial['target'] = target
      form = zfs_forms.CreateSnapshotForm(initial=initial, datasets = datasets)
      return_dict['form'] = form
      return django.shortcuts.render_to_response("create_zfs_snapshot.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = zfs_forms.CreateSnapshotForm(request.POST, datasets = datasets)
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("create_zfs_snapshot.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      if request.POST.get("id_scheduler"):
        target = cd['target']
        result, err = zfs.get_create_snapshot_command(target)
        if err:
          raise Exception(err)
        if result:
          # <QueryDict: {u'is_scheduler': [u'on'], u'target': [u'pool1'], u'is_week': [u''], u'is_hour': [u'', u''], u'is_month': [u'', u''], u'name': [u'snap1']}> /sbin/zfs snapshot pool1@snap1
          min = request.POST.get('id_minute')
          hour = request.POST.get('id_hour')
          day_of_month = request.POST.get('id_day_of_month')
          month = request.POST.get('id_month')
          week = request.POST.get('id_week')
          result = result + "$(date +\%d-\%m-\%Y-\%I-\%M)"
          msg,err = scheduler_utils.create_cron("ZFS Snapshot Creation",min,hour,day_of_month,month,week,result,None)
          if msg:
            return_dict["conf"] = "Snapshot Schedule Successful"
          else:
            return_dict["conf"] = "Snapshot Schedule Unsuccessful"
      else:
        result, err = zfs.create_snapshot(cd['target'], cd['name'])
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Created a ZFS snapshot named %s for target %s"%(cd['name'], cd['target'])
      audit.audit("create_zfs_snapshot", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_snapshots?action=created')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Create a ZFS snapshot'
    return_dict['tab'] = 'view_zfs_snapshots_tab'
    return_dict["error"] = 'Error creating a ZFS snapshot'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def delete_zfs_snapshot(request):

  return_dict = {}
  try:
    if 'name' not in request.REQUEST:
      raise Exception("No snapshot name specified. Please use the menus")
    name = request.REQUEST["name"]
    if 'display_name' in request.REQUEST:
      return_dict["display_name"] = request.REQUEST['display_name']
    return_dict["name"] = name

    if request.method == "GET":
      #Return the conf page
      return django.shortcuts.render_to_response("delete_zfs_snapshot_conf.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      result, err = zfs.delete_snapshot(name)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Deleted ZFS snapshot %s"%name
      audit.audit("delete_zfs_snapshot", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_snapshots?action=deleted')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Delete a ZFS snapshot'
    return_dict['tab'] = 'view_zfs_snapshots_tab'
    return_dict["error"] = 'Error deleting a ZFS snapshot'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def rollback_zfs_snapshot(request):

  return_dict = {}
  try:
    if 'name' not in request.REQUEST:
      raise Exceptio("No snapshot name specified. Please use the menus")
    name = request.REQUEST["name"]
    if 'display_name' in request.REQUEST:
      return_dict["display_name"] = request.REQUEST['display_name']
    return_dict["name"] = name

    if request.method == "GET":
      #Return the conf page
      return django.shortcuts.render_to_response("rollback_zfs_snapshot_conf.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      result, err = zfs.rollback_snapshot(name)
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Rolled back to ZFS snapshot %s"%name
      audit.audit("rollback_zfs_snapshot", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_snapshots?action=rolled_back')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Rollback a ZFS snapshot'
    return_dict['tab'] = 'view_zfs_snapshots_tab'
    return_dict["error"] = 'Error rolling back a  ZFS snapshot'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def rename_zfs_snapshot(request):
  return_dict = {}
  try:
    if request.method == "GET":
      if ('ds_name' not in request.GET) or ('snapshot_name' not in request.GET):
        raise Exception("Required info not passed. Please use the menus.")

      ds_name = request.GET['ds_name']
      snapshot_name = request.GET['snapshot_name']
      #Return the conf page
      initial = {}
      initial['snapshot_name'] = snapshot_name
      initial['ds_name'] = ds_name
      form = zfs_forms.RenameSnapshotForm(initial=initial)
      return_dict['form'] = form
      return django.shortcuts.render_to_response("rename_zfs_snapshot.html", return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = zfs_forms.RenameSnapshotForm(request.POST)
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("rename_zfs_snapshot.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      result, err = zfs.rename_snapshot(cd['ds_name'], cd['snapshot_name'], cd['new_snapshot_name'])
      if not result:
        if not err:
          raise Exception('Unknown error!')
        else:
          raise Exception(err)
 
      audit_str = "Renamed  ZFS snapshot for %s from %s to %s"%(cd['ds_name'], cd['snapshot_name'], cd['new_snapshot_name'])
      audit.audit("rename_zfs_snapshot", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_zfs_snapshots?action=renamed')
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Rename a ZFS snapshot'
    return_dict['tab'] = 'view_zfs_snapshots_tab'
    return_dict["error"] = 'Error renaming a loading ZFS snapshot'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def replace_disk(request):

  return_dict = {}
  try:
    form = None
  
    si, err = system_info.load_system_config()
    if err:
      raise Exception(err)
    if not si:
      raise Exception('Error loading system config')

    return_dict['system_config_list'] = si
    
    template = 'logged_in_error.html'
    use_salt, err = common.use_salt()
    if err:
      raise Exception(err)
  
    if request.method == "GET":
      raise Exception("Incorrect access method. Please use the menus")
    else:
      if 'node' in request.POST:
        node = request.POST["node"]
      else:
        node = si.keys()[0]
      serial_number = request.POST["serial_number"]
  
      if "conf" in request.POST:
        if "node" not in request.POST or  "serial_number" not in request.POST:
          raise Exception("Incorrect access method. Please use the menus")
        elif request.POST["node"] not in si:
          raise Exception("Unknown node. Please use the menus")
        elif "step" not in request.POST :
          raise Exception("Incomplete request. Please use the menus")
        elif request.POST["step"] not in ["offline_disk", "scan_for_new_disk", "online_new_disk"]:
          raise Exception("Incomplete request. Please use the menus")
        else:
          step = request.POST["step"]
  
          # Which step of the replace disk are we in?
  
          if step == "offline_disk":
  
            #get the pool corresponding to the disk
            #zpool offline pool disk
            #send a screen asking them to replace the disk
  
            pool = None
            if serial_number in si[node]["disks"]:
              disk = si[node]["disks"][serial_number]
              if "pool" in disk:
                pool = disk["pool"]
              disk_id = disk["id"]
            if not pool:
              raise Exception("Could not find the storage pool on that disk. Please use the menus")
            else:
              cmd_to_run = 'zpool offline %s %s'%(pool, disk_id)
              #print 'Running %s'%cmd_to_run
              #assert False
              if use_salt:
                #issue a zpool offline pool disk-id using salt
                client = salt.client.LocalClient()
                rc = client.cmd(node, 'cmd.run_all', [cmd_to_run])
                if rc:
                  for node, ret in rc.items():
                    #print ret
                    if ret["retcode"] != 0:
                      error = "Error bringing the disk with serial number %s offline on %s : "%(serial_number, node)
                      if "stderr" in ret:
                        error += ret["stderr"]
                      raise Exception(error)
                #print rc
              else:
                (ret, rc), err = integralstor_common.common.command.execute_with_rc(cmd_to_run)
                if err:
                  raise Exception(err)
                #print ret
                if rc != 0:
                  err = "Error bringing the disk with serial number %s offline  : "%(serial_number)
                  tl, er = command.get_output_list(ret)
                  if er:
                    raise Exception(er)
                  if tl:
                    err = ','.join(tl)
                  tl, er = command.get_error_list(ret)
                  if er:
                    raise Exception(er)
                  if tl:
                    err = err + ','.join(tl)
                  raise Exception(err)  
              #if disk_status == "Disk Missing":
              #  #Issue a reboot now, wait for a couple of seconds for it to shutdown and then redirect to the template to wait for reboot..
              #  pass
              return_dict["serial_number"] = serial_number
              return_dict["node"] = node
              return_dict["pool"] = pool
              return_dict["old_id"] = disk_id
              template = "replace_disk_prompt.html"
  
          elif step == "scan_for_new_disk":
  
            #they have replaced the disk so scan for the new disk
            # and prompt for a confirmation of the new disk serial number
  
            pool = request.POST["pool"]
            old_id = request.POST["old_id"]
            return_dict["node"] = node
            return_dict["serial_number"] = serial_number
            return_dict["pool"] = pool
            return_dict["old_id"] = old_id
            old_disks = si[node]["disks"].keys()
            if use_salt:
              client = salt.client.LocalClient()
              rc = client.cmd(node, 'integralstor.disk_info_and_status')
            else:
              rc, err = manifest_status.disk_info_and_status()
              if err:
                raise Exception(err)
            if rc and node in rc:
              new_disks = rc[node].keys()
              if new_disks:
                for disk in new_disks:
                  if disk not in old_disks:
                    return_dict["inserted_disk_serial_number"] = disk
                    return_dict["new_id"] = rc[node][disk]["id"]
                    break
                if "inserted_disk_serial_number" not in return_dict:
                  raise Exception("Could not detect any new disk.")
                else:
                  template = "replace_disk_confirm_new_disk.html"
          elif step == "online_new_disk":
  
            python_scripts_path, err = integralstor_common.common.get_python_scripts_path()
            if err:
              raise Exception(err)
            #they have confirmed the new disk serial number
            #get the id of the disk and
            #zpool replace poolname old disk new disk
            #zpool clear poolname to clear old errors
            #return a result screen
            pool = request.POST["pool"]
            old_id = request.POST["old_id"]
            new_id = request.POST["new_id"]
            new_serial_number = request.POST["new_serial_number"]
            cmd_to_run = "zpool replace -f %s %s %s"%(pool, old_id, new_id)
            if use_salt:
              #print 'Running %s'%cmd_to_run
              client = salt.client.LocalClient()
              rc = client.cmd(node, 'cmd.run_all', [cmd_to_run])
              if rc:
                #print rc
                for node, ret in rc.items():
                  #print ret
                  if ret["retcode"] != 0:
                    error = "Error replacing the disk on %s : "%(node)
                    if "stderr" in ret:
                      error += ret["stderr"]
                    rc = client.cmd(node, 'cmd.run', ['zpool online %s %s'%(pool, old_id)])
                    raise Exception(error) 
              else:
                raise Exception("Error replacing the disk on %s : "%(node))
            else:
                (ret, rc), err = integralstor_common.common.command.execute_with_rc(cmd_to_run)
                if err:
                  raise Exception(err)
                #print ret
                if rc != 0:
                  err = "Error replacing the disk  : "
                  tl, er = command.get_output_list(ret)
                  if er:
                    raise Exception(er)
                  if tl:
                    err = ','.join(tl)
                  tl, er = command.get_error_list(ret)
                  if er:
                    raise Exception(er)
                  if tl:
                    err = err + ','.join(tl)
                  raise Exception(err)
            '''
            cmd_to_run = "zpool set autoexpand=on %s"%pool
            if use_salt:
              print 'Running %s'%cmd_to_run
              rc = client.cmd(node, 'cmd.run_all', [cmd_to_run])
              if rc:
                for node, ret in rc.items():
                  #print ret
                  if ret["retcode"] != 0:
                    error = "Error setting pool autoexpand on %s : "%(node)
                    if "stderr" in ret:
                      error += ret["stderr"]
                    return_dict["error"] = error
                    return django.shortcuts.render_to_response('logged_in_error.html', return_dict, context_instance = django.template.context.RequestContext(request))
              print rc
            else:
              (ret, rc), err = integralstor_common.common.command.execute_with_rc(cmd_to_run)
              if err:
                raise Exception(err)
              #print ret
              if rc != 0:
                err = "Error setting pool autoexpand on %s : "%(node)
                tl, er = command.get_output_list(ret)
                if er:
                  raise Exception(er)
                if tl:
                  err = ','.join(tl)
                tl, er = command.get_error_list(ret)
                if er:
                  raise Exception(er)
                if tl:
                  err = err + ','.join(tl)
                return_dict["error"] = err
                return django.shortcuts.render_to_response('logged_in_error.html', return_dict, context_instance = django.template.context.RequestContext(request))
            if new_serial_number in si[node]["disks"]:
              disk = si[node]["disks"][new_serial_number]
              disk_id = disk["id"]
            '''
            cmd_to_run = 'zpool online %s %s'%(pool, new_id)
            if use_salt:
              #print 'Running %s'%cmd_to_run
              rc = client.cmd(node, 'cmd.run_all', [cmd_to_run])
              if rc:
                #print rc
                for node, ret in rc.items():
                  #print ret
                  if ret["retcode"] != 0:
                    error = "Error bringing the new disk online on %s : "%(node)
                    if "stderr" in ret:
                      error += ret["stderr"]
                    raise Exception(error)
              else:
                raise Exception("Error bringing the new disk online on %s : "%(node))
            else:
              (ret, rc), err = integralstor_common.common.command.execute_with_rc(cmd_to_run)
              if err:
                raise Exception(err)
              #print ret
              if rc != 0:
                err = "Error bringing the new disk online  : "
                tl, er = command.get_output_list(ret)
                if er:
                  raise Exception(er)
                if tl:
                  err = ','.join(tl)
                tl, er = command.get_error_list(ret)
                if er:
                  raise Exception(er)
                if tl:
                  err = err + ','.join(tl)
                raise Exception(err)
            (ret, rc), err = integralstor_common.common.command.execute_with_rc('%s/generate_manifest.py'%python_scripts_path)
            if err:
              raise Exception(err)
            #print ret
            if rc != 0:
              err = ""
              tl, er = command.get_output_list(ret)
              if er:
                raise Exception(er)
              if tl:
                err = ','.join(tl)
              tl, er = command.get_error_list(ret)
              if er:
                raise Exception(er)
              if tl:
                err = err + ','.join(tl)
              raise Exception("Could not regenrate the new hardware configuration. Error generating manifest. %s"%err)
              #print ret
            else:
              (ret, rc), err = integralstor_common.common.command.execute_with_rc('%s/generate_status.py'%python_scripts_path)
              if err:
                raise Exception(err)
              if rc != 0:
                err = ""
                tl, er = command.get_output_list(ret)
                if er:
                  raise Exception(er)
                if tl:
                  err = ','.join(tl)
                tl, er = command.get_error_list(ret)
                if er:
                  raise Exception(er)
                if tl:
                  err = err + ','.join(tl)
                raise Exception("Could not regenrate the new hardware configuration. Error generating status. %s"%err)
                #print ret
              si, err = system_info.load_system_config()
              if err:
                raise Exception(err)
              return_dict["node"] = node
              return_dict["old_serial_number"] = serial_number
              return_dict["new_serial_number"] = new_serial_number
              template = "replace_disk_success.html"
  
          return django.shortcuts.render_to_response(template, return_dict, context_instance = django.template.context.RequestContext(request))
          
      else:
        if "serial_number" not in request.POST:
          raise Exception("Incorrect access method. Please use the menus")
        else:
          if 'node' in request.POST:
            return_dict["node"] = request.POST["node"]
          else:
            node = si.keys()[0]
          return_dict["serial_number"] = request.POST["serial_number"]
          template = "replace_disk_conf.html"
    return django.shortcuts.render_to_response(template, return_dict, context_instance=django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "dashboard_base.html"
    return_dict["page_title"] = 'Replace a hard drive'
    return_dict['tab'] = 'disks_tab'
    return_dict["error"] = 'Error replacing hard drive'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def modify_dir_permissions(request):
  return_dict = {}
  try:
    if 'path' not in request.REQUEST:
      path = "/pool/ds1/test3/"
      #raise Exception('Path not specified')
    else:
      path = request.REQUEST['path']
    users, err = local_users.get_local_users()
    if err:
      raise Exception('Error retrieving local user list : %s'%err)
    if not users:
      raise Exception('No local users seem to be created. Please create at least one local user before performing this operation.')

    groups, err = local_users.get_local_groups()
    if err:
      raise Exception('Error retrieving local group list : %s'%err)
    if not groups:
      raise Exception('No local groups seem to be created. Please create at least one local group before performing this operation.')

    try:
      stat_info = os.stat(path)
    except Exception, e:
      raise Exception('Error accessing specified path : %s'%str(e))
    uid = stat_info.st_uid
    gid = stat_info.st_gid
    username = pwd.getpwuid(uid)[0]
    grpname = grp.getgrgid(gid)[0]
    return_dict["username"] = username
    return_dict["grpname"] = grpname
    pools, err = zfs.get_pools()
    ds_list = [] 
    for pool in pools:
      for ds in pool["datasets"]:
        if ds['properties']['type']['value'] == 'filesystem':
          ds_list.append(ds["name"])
    if not ds_list:
      raise Exception('No ZFS datasets available. Please create a dataset before creating shares.')
    return_dict["dataset"] = ds_list
    if request.method == "GET":
      # Shd be an edit request
  
      # Set initial form values
      initial = {}
      initial['path'] = path
      initial['owner_read'] = _owner_readable(stat_info)
      initial['owner_write'] = _owner_writeable(stat_info)
      initial['owner_execute'] = _owner_executeable(stat_info)
      initial['group_read'] = _group_readable(stat_info)
      initial['group_write'] = _group_writeable(stat_info)
      initial['group_execute'] = _group_executeable(stat_info)
      initial['other_read'] = _other_readable(stat_info)
      initial['other_write'] = _other_writeable(stat_info)
      initial['other_execute'] = _other_executeable(stat_info)
  
      form = common_forms.SetFileOwnerAndPermissionsForm(initial = initial, user_list = users, group_list = groups)
  
      return_dict["form"] = form
      return django.shortcuts.render_to_response('modify_dir_permissions.html', return_dict, context_instance=django.template.context.RequestContext(request))
  
    else:
      # Shd be an save request
      form = common_forms.SetFileOwnerAndPermissionsForm(request.POST, user_list = users, group_list = groups)
      return_dict["form"] = form
      if form.is_valid():
        cd = form.cleaned_data
        ret, err = file_processing.set_dir_ownership_and_permissions(cd)
        if not ret:
          if err:
            raise Exception(err)
          else:
            raise Exception("Error setting directory ownership/permissions.")
  
        audit_str = "Modified directory ownsership/permissions for %s"%cd["path"]
        audit.audit("modify_dir_owner_permissions", audit_str, request.META["REMOTE_ADDR"])
  
        return django.http.HttpResponseRedirect('/view_zfs_pools?action=set_permissions')
  
      else:
        #Invalid form
        return django.shortcuts.render_to_response('modify_dir_permissions.html', return_dict, context_instance=django.template.context.RequestContext(request))
  except Exception, e:
    return_dict['base_template'] = "storage_base.html"
    return_dict["page_title"] = 'Modify ownership/permissions on a directory'
    return_dict['tab'] = 'dir_permissions_tab'
    return_dict["error"] = 'Error modifying directory ownership/permissions'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def _owner_readable(st):
  return bool(st.st_mode & stat.S_IRUSR)
def _owner_writeable(st):
  return bool(st.st_mode & stat.S_IWUSR)
def _owner_executeable(st):
  return bool(st.st_mode & stat.S_IXUSR)

def _group_readable(st):
  return bool(st.st_mode & stat.S_IRGRP)
def _group_writeable(st):
  return bool(st.st_mode & stat.S_IWGRP)
def _group_executeable(st):
  return bool(st.st_mode & stat.S_IXGRP)

def _other_readable(st):
  return bool(st.st_mode & stat.S_IROTH)
def _other_writeable(st):
  return bool(st.st_mode & stat.S_IWOTH)
def _other_executeable(st):
  return bool(st.st_mode & stat.S_IXOTH)
