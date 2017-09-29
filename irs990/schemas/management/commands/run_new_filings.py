import json
from django.core.management.base import BaseCommand
#from django.conf import settings
from irsx.xmlrunner import XMLRunner
from irsx.filing import Filing
from irsx.standardizer import Standardizer
from filing.models import xml_submission as XMLSubmission, ProcessedFiling
from filing.type_utils import unicodeType
from schemas.model_accumulator import Accumulator


BATCHSIZE = 100
LOOP_MAX = 100
ids = ['201531059349300953', '201531059349300963', '201531049349200813', '201531049349201053', '201531069349200108', '201531069349200703', '201541049349200129', '201541049349200204', '201541049349200329', '201541049349200429', '201501019349200000', '201501039349200030', '201501039349200130', '201501039349200200', '201531069349300613', '201501059349200715', '201501059349200810', '201501059349200815', '201501059349200840', '201501059349201075', '201501059349201165', '201511009349200751', '201511019349200406', '201511049349200426', '201511049349200516', '201511049349200521', '201511049349200706', '201521009349200757', '201521009349200767', '201521059349200202', '201521059349200247', '201521059349200407', '201521059349200417', '201521059349200427', '201531019349200113', '201531019349200403', '201531059349300988', '201531059349301093', '201531059349301098', '201531059349301108', '201531059349301128', '201531059349301143', '201531059349301173', '201531059349301203']
def processed_filing_from_result_filing(completed_filing, parent_submission):
    """ Turn the returned filing object into an unsaved ProcessedFiling  """

    newpf = ProcessedFiling(
        ein = completed_filing.get_ein(),
        object_id = completed_filing.get_object_id(),
        version_string = completed_filing.get_version(),
        processed_json = json.dumps(completed_filing.get_result()),
        has_keyerrors = False,
        submission = parent_submission,
        is_saved = False
    )

    keyerrors = completed_filing.get_keyerrors()
    if keyerrors:
        newpf.has_keyerrors = True 
        newpf.keyerrors = completed_filing.get_keyerrors()

    return newpf

class Command(BaseCommand):
    help = 'Enter new files, as json an in the relational tables. '


    def process_sked(self, sked):
        """ Enter just one schedule """ 
        #print("Processing schedule %s" % sked['schedule_name'])
        for part in sked['schedule_parts'].keys():
            partname = part
            partdata = sked['schedule_parts'][part]

            self.accumulator.add_model(partname, partdata)

        for groupname in sked['groups'].keys():
            for groupdata in sked['groups'][groupname]:
                #print("group %s " % (groupname))
                #try:
                #    # hack for testing some older data
                #    groupdata['object_id']=groupdata['return_id']
                #    del groupdata['return_id']
                #except KeyError:
                #    pass
                if  groupname == 'null':    # wtf?
                    print("\n\n\n%s" % groupdata)
                else:
                    self.accumulator.add_model(groupname, groupdata)


    def enter_from_result(self, result):
        for sked in result:
            #print ("running from result %s" % sked)
            self.process_sked(sked)


    def process_batch(self, xml_submission_queryset):
        newpf_list = []
        for xml_submission in xml_submission_queryset:

            print("Handling object id %s sub_date=%s." % (xml_submission.object_id, xml_submission.sub_date))
            try:
                exists = ProcessedFiling.objects.get(object_id=xml_submission.object_id)
            except ProcessedFiling.DoesNotExist:
                completed_filing = self.xml_runner.run_filing(xml_submission.object_id)

                new_pf = processed_filing_from_result_filing(completed_filing, xml_submission)
                
                xml_submission.json_set=True
                xml_submission.save()

                raw_json = new_pf.processed_json
                if not raw_json:
                    print ("No raw json -- skipping %s" % xml_submission.object_id)
                    continue

                read_json = json.loads(raw_json)
                if not read_json:
                    print ("No json loaded -- skipping %s" % xml_submission.object_id)
                    continue
                if type(read_json)==unicodeType:
                    self.enter_from_result(json.loads(read_json))
                else:
                    self.enter_from_result(read_json)
                new_pf.is_saved = True

                newpf_list.append(new_pf)

        
                self.accumulator.commit_all() # for testing, should go at the end when running. 
        #self.accumulator.commit_all()


        print("Processing %s filings in bulk" % len(newpf_list))
        ProcessedFiling.objects.bulk_create(newpf_list)

            

    def handle(self, *args, **options):
        self.xml_runner = XMLRunner()
        self.accumulator = Accumulator()

        count = 0
        while True:
            #xml_batch = XMLSubmission.objects.filter(year=2015).exclude(json_set=True)[:BATCHSIZE]
            #xml_batch = XMLSubmission.objects.filter(object_id__in=ids).exclude(json_set=True)[:BATCHSIZE]
            xml_batch = XMLSubmission.objects.filter(object_id__in=['201531059349301203',])[:BATCHSIZE]
            #xml_batch = XMLSubmission.objects.filter(object_id__in=test2016ids).exclude(json_set=True)[:BATCHSIZE]
            #xml_batch = XMLSubmission.objects.filter(sub_date__regex=r'^8.+2017.*').exclude(json_set=True)[:BATCHSIZE]
            #xml_batch = XMLSubmission.objects.filter(object_id__in=test2016ids).exclude(json_set=True)[:BATCHSIZE]
            #xml_batch = XMLSubmission.objects.filter(object_id__in=['201601349349304030',])


            count += 1
            print count
            if len(xml_batch)==0:
                break

            self.process_batch(xml_batch)


            # for testing
            if count > LOOP_MAX:
                break
